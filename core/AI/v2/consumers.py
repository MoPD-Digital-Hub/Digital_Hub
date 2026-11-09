import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from AI.models import ChatInstance
from AI.v2.pipeline import answer_stream

LOGGER = logging.getLogger(__name__)


class ChatConsumerV2(AsyncWebsocketConsumer):
    """/ws/v2/chat/<chat_instance_id>/

    Send {"message": "..."}; receive the events described in AI.v2.pipeline.
    One question at a time per connection: a second question sent while an
    answer is streaming gets an error event.
    """

    async def connect(self):
        self.instance = await self._instance(self.scope["url_route"]["kwargs"]["room_name"], self.scope.get("user"))
        if self.instance is None:
            await self.close(code=4404)
            return
        self.busy = False
        await self.accept()

    @database_sync_to_async
    def _instance(self, room_name, user):
        instances = ChatInstance.objects.filter(id=room_name, is_deleted=False)
        # Match v1, which lets unauthenticated clients in, but never let one
        # signed-in user open another user's conversation.
        if user is not None and getattr(user, "is_authenticated", False):
            instances = instances.filter(user=user)
        return instances.first()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            question = str(json.loads(text_data or "{}").get("message", "")).strip()
        except (ValueError, AttributeError):
            question = ""
        if not question:
            await self._send({"type": "error", "message": "Send {\"message\": \"your question\"}."})
            return
        if self.busy:
            await self._send({"type": "error", "message": "Wait for the current answer to finish."})
            return

        self.busy = True
        try:
            async for event in answer_stream(question, instance=self.instance):
                await self._send(event)
        except Exception:
            LOGGER.exception("v2 socket answer failed")
            await self._send({"type": "error", "message": "Something went wrong. Please try again."})
        finally:
            self.busy = False

    async def _send(self, event):
        await self.send(text_data=json.dumps(event, ensure_ascii=False))
