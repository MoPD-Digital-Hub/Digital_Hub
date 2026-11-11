import asyncio
import json
import re
from html import unescape

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from ai.engine import compat

WS_SEMAPHORE = asyncio.Semaphore(max(1, getattr(settings, "AI_WS_MAX_CONCURRENCY", 20)))


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
        # Browsers always send Origin; the Flutter app sends none (see
        # chat.middleware.MobileFriendlyOriginValidator).
        self.is_native_client = not any(name == b"origin" for name, _ in self.scope.get("headers", []))
        self.instance_id = await self.get_instance_id(self.room_name, self.scope.get("user"))

        if not self.instance_id:
            await self.close()
            return

        await self.accept()
        await self.after_accept()

    async def after_accept(self):
        """Hook for subclasses."""
        return

    async def receive(self, text_data):
        async with WS_SEMAPHORE:
            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                return

            question_text = str(payload.get("message", "")).strip()
            if not question_text:
                return

            instance = await self.get_instance(self.instance_id)
            if instance is None:
                return
            await compat.stream_answer(
                question_text,
                instance=instance,
                send=lambda message: self.send(text_data=json.dumps(message)),
                is_native_client=self.is_native_client,
                preview=_build_stream_preview,
            )

    @database_sync_to_async
    def get_instance_id(self, room_name, user=None):
        from .models import ChatInstance

        instances = ChatInstance.objects.filter(id=room_name, is_deleted=False)
        # Unauthenticated clients are let in (the app's sockets may not send a
        # token), but a signed-in user can only open their own conversation.
        if user is not None and getattr(user, "is_authenticated", False):
            instances = instances.filter(user=user)
        instance = instances.first()
        return instance.id if instance else None

    @database_sync_to_async
    def get_instance(self, instance_id):
        from .models import ChatInstance

        return ChatInstance.objects.filter(id=instance_id, is_deleted=False).first()

    @database_sync_to_async
    def get_history(self, instance_id):
        from .models import QuestionHistory

        return list(
            QuestionHistory.objects.filter(instance_id=instance_id)
            .order_by("created_at")
            .values("question", "response")
        )


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

