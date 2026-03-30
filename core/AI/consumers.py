import asyncio
import json
import logging
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from AI.models import ChatInstance, QuestionHistory
from AI.orchestration import AIOrchestrator, OrchestrationError

LOGGER = logging.getLogger("AI.websocket")
GENERIC_INSTANCE_TITLES = {"", "new chat", "new instance"}


def _looks_generic_title(title: str) -> bool:
    return str(title or "").strip().lower() in GENERIC_INSTANCE_TITLES


def _build_instance_title(question: str) -> str:
    text = re.sub(r"\s+", " ", str(question or "").strip())
    if not text:
        return "General Chat"
    text = re.sub(r"[?.!]+$", "", text).strip()
    if len(text) <= 60:
        return text
    shortened = text[:57].rsplit(" ", 1)[0].strip()
    return (shortened or text[:57].strip()) + "..."


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.instance = await self._get_instance(self.room_name)
        user = self.scope.get("user")
        if self.instance is None or user is None or not user.is_authenticated:
            await self.close()
            return
        if self.instance.user_id != user.id:
            await self.close()
            return
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self._send_error("INVALID_PAYLOAD", "Invalid WebSocket payload.")
            return

        question = str(payload.get("message") or "").strip()
        if not question:
            await self._send_error("QUESTION_REQUIRED", "message is required.")
            return

        history = await self._get_history(self.instance.id)
        record_id = await self._create_question(self.instance.id, question)
        orchestrator = AIOrchestrator()
        chunks = []
        latest_usage = None
        response_language = None
        latest_charts = []
        latest_intent = "general_query"
        latest_response_type = ""
        latest_secondary_intents = []
        latest_tool_data = {}
        latest_tool_state = {}
        latest_sources = []
        latest_context_found = False

        try:
            async for event in orchestrator.stream(question=question, history_records=history):
                chunk = event.get("text") or ""
                latest_charts = event.get("charts") or latest_charts
                latest_intent = event.get("intent") or latest_intent
                latest_response_type = event.get("response_type") or latest_response_type
                latest_secondary_intents = event.get("secondary_intents") or latest_secondary_intents
                latest_tool_data = event.get("data") or latest_tool_data
                latest_tool_state = event.get("tool_state") or latest_tool_state
                latest_sources = event.get("sources") or latest_sources
                latest_context_found = event.get("context_found", latest_context_found)
                if not chunk:
                    continue
                chunks.append(chunk)
                latest_usage = event.get("usage") or latest_usage
                response_language = event.get("language") or response_language
                await self.send(
                    text_data=json.dumps(
                        {
                            "message": chunk,
                            "is_stream": True,
                            "is_final": False,
                            "language": event.get("language"),
                        }
                    )
                )
                await asyncio.sleep(0)
        except OrchestrationError as exc:
            await self._save_response(record_id, exc.message)
            await self._send_error(exc.code, exc.message)
            return

        answer = "".join(chunks).strip()
        if not answer:
            answer = "<p>No response was generated.</p>"
        persisted_tool_data = self._merge_tool_state(
            latest_tool_state,
            payload=latest_tool_data,
            sources=latest_sources,
            charts=latest_charts,
            context_found=latest_context_found,
            language=response_language,
            intent=latest_intent,
            secondary_intents=latest_secondary_intents,
            usage=latest_usage,
        )
        chat_title = await self._save_response(
            record_id,
            answer,
            question=question,
            retrieval_charts=latest_charts,
            tool_data=persisted_tool_data,
        )
        await self.send(
            text_data=json.dumps(
                {
                    "intent": latest_intent,
                    "response_type": latest_response_type,
                    "secondary_intents": latest_secondary_intents,
                    "message": answer,
                    "is_stream": False,
                    "is_final": True,
                    "language": response_language,
                    "usage": latest_usage,
                    "charts": latest_charts,
                    "tool_data": persisted_tool_data,
                    "response_data": latest_tool_data,
                    "sources": latest_sources,
                    "context_found": latest_context_found,
                    "chat_title": chat_title,
                }
            )
        )

    async def _send_error(self, code, detail):
        await self.send(
            text_data=json.dumps(
                {
                    "error": {
                        "code": code,
                        "message": detail,
                    },
                    "is_final": True,
                }
            )
        )

    @database_sync_to_async
    def _get_instance(self, room_name):
        return ChatInstance.objects.filter(id=room_name, is_deleted=False).first()

    @database_sync_to_async
    def _get_history(self, instance_id):
        return list(
            QuestionHistory.objects.filter(instance_id=instance_id)
            .exclude(response__isnull=True)
            .exclude(response="")
            .order_by("created_at")
            .values("question", "response", "tool_data", "chart_data")
        )

    @database_sync_to_async
    def _create_question(self, instance_id, question):
        record = QuestionHistory.objects.create(instance_id=instance_id, question=question)
        return record.id

    @database_sync_to_async
    def _save_response(self, record_id, answer, question="", retrieval_charts=None, tool_data=None):
        QuestionHistory.objects.filter(id=record_id).update(
            response=answer,
            chart_data=list(retrieval_charts or []),
            tool_data=dict(tool_data or {}),
        )
        record = QuestionHistory.objects.select_related("instance").filter(id=record_id).first()
        if record and record.instance and _looks_generic_title(record.instance.title):
            record.instance.title = _build_instance_title(question)
            record.instance.save(update_fields=["title"])
        return record.instance.title if record and record.instance else ""

    def _merge_tool_state(self, tool_state, *, payload=None, sources=None, charts=None, context_found=False, language=None, intent=None, secondary_intents=None, usage=None):
        merged = dict(tool_state or {})
        if payload:
            merged["payload"] = dict(payload)
            if isinstance(payload, dict):
                if "data" in payload:
                    merged["response_payload"] = dict(payload)
                    merged["primary_data"] = dict(payload.get("data") or {})
                    merged["supporting_context"] = dict((payload.get("data") or {}).get("supporting_context") or {})
                if "primary_data" in payload:
                    merged["primary_data"] = dict(payload.get("primary_data") or {})
                if "supporting_context" in payload:
                    merged["supporting_context"] = dict(payload.get("supporting_context") or {})
                if "response_type" in payload:
                    merged["response_type"] = payload.get("response_type")
        last_tool_result = dict(merged.get("last_tool_result") or {})
        if sources:
            last_tool_result["sources"] = list(sources)
        if charts:
            last_tool_result["charts"] = list(charts)
        last_tool_result["context_found"] = bool(context_found)
        if usage:
            last_tool_result["usage"] = dict(usage)
        if last_tool_result:
            merged["last_tool_result"] = last_tool_result
        if language:
            merged["language"] = language
        if intent:
            merged["intent"] = intent
        if secondary_intents:
            merged["secondary_intents"] = list(secondary_intents)
        return merged
