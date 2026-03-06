import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from AI.domain import INTENTS
from AI.platform.exceptions import AIServiceError
from AI.platform.observability import increment
from AI.infrastructure import get_llm_instance
from AI.selectors import build_context_for_intent, resolve_intent
from AI.services import format_history_records_for_llm, retrieve_docs
from AI.shared import run_chain_stream

LOGGER = logging.getLogger("AI.consumers")
WS_SEMAPHORE = asyncio.Semaphore(max(1, getattr(settings, "AI_WS_MAX_CONCURRENCY", 20)))

NO_DOCS_MESSAGE = "No relevant indicator found in the knowledge base for this query."


class BaseAIConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        self.instance_id = await self.get_instance_id(self.room_name)

        if not self.instance_id:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.after_accept()

    async def after_accept(self):
        """Hook for subclasses."""
        return

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        async with WS_SEMAPHORE:
            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                return

            question_text = str(payload.get("message", "")).strip()
            if not question_text:
                return

            await self.save_question(self.instance_id, question_text)

            llm = get_llm_instance()
            try:
                docs = retrieve_docs(question_text)
            except AIServiceError:
                await self._finalize_answer(
                    "<p>Retriever dependency is unavailable. Please try again later.</p>",
                    intent=INTENTS["UNKNOWN"],
                )
                return

            if not docs:
                increment("ws_retrieval_empty")
                await self._finalize_answer(NO_DOCS_MESSAGE, intent=INTENTS["UNKNOWN"])
                return

            intent = resolve_intent(llm, question_text, docs)
            context = build_context_for_intent(intent, llm, question_text, docs)

            history = await self.get_history(self.instance_id)
            conversation_list = format_history_records_for_llm(history)

            chunks = []
            async for chunk in run_chain_stream(llm, conversation_list, context, question_text, intent):
                if not chunk:
                    continue
                chunks.append(chunk)
                await self.send(
                    text_data=json.dumps(
                        {
                            "message": chunk,
                            "is_stream": True,
                        }
                    )
                )
                await asyncio.sleep(0)

            answer = "".join(chunks).strip() or "<p>Unable to generate a response right now. Please try again.</p>"
            await self._finalize_answer(answer, intent=intent)

    async def _finalize_answer(self, answer, intent):
        await self.save_response(self.instance_id, answer)
        await self.send(
            text_data=json.dumps(
                {
                    "message": "",
                    "is_stream": False,
                    "is_final": True,
                    "intent": intent,
                }
            )
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "is_stream": event.get("is_stream", False),
                    "is_final": event.get("is_final", False),
                }
            )
        )

    @database_sync_to_async
    def get_instance_id(self, room_name):
        from .models import ChatInstance

        instance = ChatInstance.objects.filter(id=room_name, is_deleted=False).first()
        return instance.id if instance else None

    @database_sync_to_async
    def get_history(self, instance_id):
        from .models import QuestionHistory

        return list(
            QuestionHistory.objects.filter(instance_id=instance_id)
            .order_by("created_at")
            .values("question", "response")
        )

    @database_sync_to_async
    def save_question(self, instance_id, question):
        from .models import QuestionHistory

        return QuestionHistory.objects.create(instance_id=instance_id, question=question)

    @database_sync_to_async
    def save_response(self, instance_id, response):
        from .models import QuestionHistory

        last = QuestionHistory.objects.filter(instance_id=instance_id).order_by("-created_at").first()
        if last:
            last.response = response
            last.save(update_fields=["response"])


class ChatConsumer(BaseAIConsumer):
    pass


class ChatWebConsumer(BaseAIConsumer):
    async def after_accept(self):
        history = await self.get_history(self.instance_id)
        for entry in history:
            await self.send(
                text_data=json.dumps(
                    {
                        "question": entry.get("question"),
                        "response": entry.get("response"),
                    }
                )
            )
            await asyncio.sleep(0.05)
