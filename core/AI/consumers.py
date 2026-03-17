import asyncio
import os
import json
import logging
import ssl
import re
from html import unescape

import aiohttp
import certifi
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from AI.runtime.exceptions import AIServiceError
from AI.runtime.exceptions import ERROR_RETRIEVAL_EMPTY
from AI.runtime.observability import increment
from AI.infrastructure import get_llm_instance
from AI.infrastructure.translation import translate_text_with_gemini
from AI.application import format_history_records_for_llm, prepare_answer
from AI.shared import invoke_chat_once, run_chain_stream

LOGGER = logging.getLogger("AI.consumers")
WS_SEMAPHORE = asyncio.Semaphore(max(1, getattr(settings, "AI_WS_MAX_CONCURRENCY", 20)))
GEMINI_LIVE_API_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

NO_DOCS_MESSAGE = "No relevant indicator found in the knowledge base for this query."
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _coerce_stream_text(chunk):
    if chunk is None:
        return ""

    if isinstance(chunk, str):
        return chunk

    if isinstance(chunk, list):
        parts = [_coerce_stream_text(item) for item in chunk]
        return "".join(part for part in parts if part)

    if isinstance(chunk, dict):
        if "text" in chunk:
            return _coerce_stream_text(chunk.get("text"))
        if "content" in chunk:
            return _coerce_stream_text(chunk.get("content"))
        parts = [_coerce_stream_text(value) for value in chunk.values()]
        return "".join(part for part in parts if part)

    content = getattr(chunk, "content", None)
    if content is not None and content is not chunk:
        return _coerce_stream_text(content)

    text = getattr(chunk, "text", None)
    if text is not None and text is not chunk:
        return _coerce_stream_text(text)

    return str(chunk)


def _build_stream_preview(text):
    cleaned = str(text or "")
    if not cleaned:
        return ""

    cleaned = re.sub(r"<chart-data[\s\S]*?</chart-data>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


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

            action = str(payload.get("action", "")).strip().lower()
            if action == "translate":
                await self._handle_translation(payload)
                return

            question_text = str(payload.get("message", "")).strip()
            if not question_text:
                return

            history = await self.get_history(self.instance_id)
            retrieval_history = [entry for entry in history if entry.get("response")]
            await self.save_question(self.instance_id, question_text)

            llm = get_llm_instance()
            try:
                prepared = prepare_answer(question_text, llm, history_records=retrieval_history)
            except AIServiceError as exc:
                if exc.code == ERROR_RETRIEVAL_EMPTY:
                    increment("ws_retrieval_empty")
                    await self._finalize_answer(NO_DOCS_MESSAGE, route="get_general_context")
                    return
                await self._finalize_answer(
                    "<p>Retriever dependency is unavailable. Please try again later.</p>",
                    route="get_general_context",
                )
                return
            route = prepared.route
            context = prepared.context

            history = await self.get_history(self.instance_id)
            answered_history = [entry for entry in history if entry.get("response")]
            conversation_list = (
                []
                if prepared.response_language == "Amharic"
                else format_history_records_for_llm(answered_history)
            )

            if prepared.response_language == "Amharic":
                try:
                    ai_response = await asyncio.to_thread(
                        invoke_chat_once,
                        llm,
                        conversation_list,
                        context,
                        prepared.normalized_question,
                        route,
                    )
                    answer = getattr(ai_response, "content", str(ai_response))
                    answer = await asyncio.to_thread(translate_text_with_gemini, answer, "Amharic")
                except Exception:
                    answer = "<p>Unable to generate a response right now. Please try again.</p>"
                await self._finalize_answer(answer, route=route)
                return

            chunks = []
            async for chunk in run_chain_stream(llm, conversation_list, context, prepared.normalized_question, route):
                normalized_chunk = _coerce_stream_text(chunk)
                if not normalized_chunk:
                    continue
                chunks.append(normalized_chunk)
                answer_so_far = "".join(chunks)
                await self.send(
                    text_data=json.dumps(
                        {
                            "message": normalized_chunk,
                            "preview": _build_stream_preview(answer_so_far),
                            "is_stream": True,
                        }
                    )
                )
                await asyncio.sleep(0)

            answer = "".join(chunks).strip() or "<p>Unable to generate a response right now. Please try again.</p>"
            await self._finalize_answer(answer, route=route)

    async def _handle_translation(self, payload):
        text = str(payload.get("text", "")).strip()
        request_id = str(payload.get("request_id", "")).strip()
        target_language = str(payload.get("target_language", "Amharic")).strip() or "Amharic"

        if not text:
            await self.send(
                text_data=json.dumps(
                    {
                        "action": "translation_result",
                        "request_id": request_id,
                        "ok": False,
                        "error": {"message": "Text is required for translation."},
                    }
                )
            )
            return

        try:
            translated = await asyncio.to_thread(
                translate_text_with_gemini,
                text,
                target_language,
            )
            await self.send(
                text_data=json.dumps(
                    {
                        "action": "translation_result",
                        "request_id": request_id,
                        "ok": True,
                        "translation": translated,
                        "target_language": target_language,
                    }
                )
            )
        except Exception as exc:
            await self.send(
                text_data=json.dumps(
                    {
                        "action": "translation_result",
                        "request_id": request_id,
                        "ok": False,
                        "error": {"message": str(exc)},
                    }
                )
            )

    async def _finalize_answer(self, answer, route):
        await self.save_response(self.instance_id, answer)
        await self.send(
            text_data=json.dumps(
                {
                    "message": answer,
                    "is_stream": False,
                    "is_final": True,
                    "route": route,
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


class TTSStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self._send_error("Invalid streaming payload.")
            return

        action = str(payload.get("action", "")).strip().lower()
        if action != "speak":
            await self._send_error("Unsupported action.")
            return

        text = str(payload.get("text", "")).strip()
        if not text:
            await self._send_error("Text is required for streaming speech.")
            return

        language = str(payload.get("language", "English")).strip() or "English"
        voice = str(payload.get("voice") or os.getenv("GEMINI_TTS_VOICE", "Charon")).strip() or "Charon"

        try:
            await self._stream_tts(text=text, language=language, voice=voice)
        except Exception as exc:
            LOGGER.exception("Gemini Live TTS streaming failed")
            await self._send_error(str(exc) or "Streaming speech failed.")

    async def _send_error(self, message):
        await self.send(text_data=json.dumps({"event": "error", "message": message}))

    async def _send_complete(self):
        await self.send(text_data=json.dumps({"event": "complete"}))

    async def _stream_tts(self, text, language, voice):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        model = os.getenv("GEMINI_LIVE_TTS_MODEL", "models/gemini-2.5-flash-preview-native-audio-dialog").strip()
        if not model.startswith("models/"):
            model = "models/" + model

        prompt = "Speak the following text naturally in {language}. Text: {text}".format(
            language=language,
            text=text,
        )

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                GEMINI_LIVE_API_URL,
                headers={"x-goog-api-key": api_key},
                heartbeat=30,
                receive_timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
                ssl=SSL_CONTEXT,
            ) as ws:
                await ws.send_json(
                    {
                        "setup": {
                            "model": model,
                            "generationConfig": {
                                "responseModalities": ["AUDIO"],
                                "speechConfig": {
                                    "voiceConfig": {
                                        "prebuiltVoiceConfig": {
                                            "voiceName": voice,
                                        }
                                    }
                                },
                            },
                        }
                    }
                )

                await self.send(text_data=json.dumps({"event": "start"}))
                setup_complete = False

                async for message in ws:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(message.data)

                        if data.get("setupComplete") is not None:
                            setup_complete = True
                            await ws.send_json(
                                {
                                    "clientContent": {
                                        "turns": [
                                            {
                                                "role": "user",
                                                "parts": [{"text": prompt}],
                                            }
                                        ],
                                        "turnComplete": True,
                                    }
                                }
                            )
                            continue

                        if not setup_complete:
                            continue

                        for chunk in _extract_audio_chunks(data):
                            await self.send(
                                text_data=json.dumps(
                                    {
                                        "event": "audio",
                                        "data": chunk["data"],
                                        "mime_type": chunk["mime_type"],
                                        "sample_rate": chunk["sample_rate"],
                                    }
                                )
                            )

                        server_content = data.get("serverContent") or {}
                        if server_content.get("turnComplete") or server_content.get("generationComplete"):
                            await self._send_complete()
                            await ws.close()
                            return

                        if data.get("goAway"):
                            raise RuntimeError("Gemini Live API closed the session.")

                    elif message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                        break
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        raise RuntimeError("Gemini Live API websocket error.")

        await self._send_complete()


def _extract_audio_chunks(payload):
    server_content = payload.get("serverContent") or {}
    model_turn = server_content.get("modelTurn") or {}
    parts = model_turn.get("parts") or []
    chunks = []
    for part in parts:
        inline = part.get("inlineData") or {}
        encoded_data = inline.get("data")
        if not encoded_data:
            continue
        mime_type = inline.get("mimeType") or "audio/L16;rate=24000"
        chunks.append(
            {
                "data": encoded_data,
                "mime_type": mime_type,
                "sample_rate": _extract_sample_rate(mime_type),
            }
        )
    return chunks


def _extract_sample_rate(mime_type):
    try:
        marker = "rate="
        if marker not in mime_type:
            return 24000
        return int(str(mime_type).split(marker, 1)[1].split(";", 1)[0])
    except (TypeError, ValueError, IndexError):
        return 24000
