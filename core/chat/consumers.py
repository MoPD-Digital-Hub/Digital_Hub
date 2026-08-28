import logging

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from chat import presence
from chat.services import user_group_name

LOGGER = logging.getLogger("chat.consumers")


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """One socket per user, carrying events for all of their conversations.

    Client -> server events:
        {"type": "conversation.focus", "conversation_id": <id>}
        {"type": "conversation.heartbeat"}
        {"type": "conversation.blur"}
        {"type": "typing", "conversation_id": <id>, "is_typing": true|false}

    Server -> client events (all carry "conversation_id"):
        message.new, message.read, typing, conversation.updated
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            # Accept first so the client sees close code 4401 instead of a
            # bare handshake rejection, and can react by refreshing its JWT.
            await self.accept()
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = user_group_name(user.id)
        self.focused_conversation_id = None
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        subprotocols = self.scope.get("subprotocols") or []
        if subprotocols and subprotocols[0].lower() == "bearer":
            await self.accept("bearer")
        else:
            await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "user", None) is None:
            return
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.focused_conversation_id is not None:
            await sync_to_async(presence.clear_focus)(self.user.id, self.focused_conversation_id)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")

        if event_type == "conversation.focus":
            await self._handle_focus(content.get("conversation_id"))
        elif event_type == "conversation.heartbeat":
            if self.focused_conversation_id is not None:
                await sync_to_async(presence.refresh_focus)(self.user.id, self.focused_conversation_id)
        elif event_type == "conversation.blur":
            await self._handle_blur()
        elif event_type == "typing":
            await self._handle_typing(content.get("conversation_id"), bool(content.get("is_typing", True)))

    async def chat_event(self, event):
        payload = event["payload"]
        await self.send_json(payload)

        # Live read receipts: a message delivered while the recipient is
        # looking at that conversation is immediately marked read.
        if (
            payload.get("type") == "message.new"
            and payload.get("conversation_id") == self.focused_conversation_id
            and payload.get("sender_id") != self.user.id
        ):
            await self._mark_read_and_notify(self.focused_conversation_id)

    async def _handle_focus(self, conversation_id):
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return
        if not await self._is_participant(conversation_id):
            return

        if self.focused_conversation_id is not None and self.focused_conversation_id != conversation_id:
            await sync_to_async(presence.clear_focus)(self.user.id, self.focused_conversation_id)

        self.focused_conversation_id = conversation_id
        await sync_to_async(presence.set_focus)(self.user.id, conversation_id)
        await self._mark_read_and_notify(conversation_id)

    async def _handle_blur(self):
        if self.focused_conversation_id is None:
            return
        conversation_id = self.focused_conversation_id
        self.focused_conversation_id = None
        await sync_to_async(presence.clear_focus)(self.user.id, conversation_id)

    async def _handle_typing(self, conversation_id, is_typing):
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return
        other_user_ids = await self._other_participant_ids(conversation_id)
        if other_user_ids is None:
            return
        payload = {
            "type": "typing",
            "conversation_id": conversation_id,
            "user_id": self.user.id,
            "is_typing": is_typing,
        }
        for user_id in other_user_ids:
            await self.channel_layer.group_send(
                user_group_name(user_id),
                {"type": "chat.event", "payload": payload},
            )

    async def _mark_read_and_notify(self, conversation_id):
        result = await self._mark_read(conversation_id)
        if result is None:
            return
        other_user_ids, last_read_at = result
        payload = {
            "type": "message.read",
            "conversation_id": conversation_id,
            "user_id": self.user.id,
            "last_read_at": last_read_at.isoformat(),
        }
        for user_id in other_user_ids:
            await self.channel_layer.group_send(
                user_group_name(user_id),
                {"type": "chat.event", "payload": payload},
            )

    @database_sync_to_async
    def _is_participant(self, conversation_id):
        from chat.models import ConversationParticipant

        return ConversationParticipant.objects.filter(
            conversation_id=conversation_id, user=self.user
        ).exists()

    @database_sync_to_async
    def _other_participant_ids(self, conversation_id):
        """Returns the other participants' user ids, or None when the
        requesting user is not a participant."""
        from chat.models import ConversationParticipant

        participants = list(
            ConversationParticipant.objects.filter(conversation_id=conversation_id).values_list("user_id", flat=True)
        )
        if self.user.id not in participants:
            return None
        return [user_id for user_id in participants if user_id != self.user.id]

    @database_sync_to_async
    def _mark_read(self, conversation_id):
        from chat.models import ConversationParticipant

        now = timezone.now()
        updated = ConversationParticipant.objects.filter(
            conversation_id=conversation_id, user=self.user
        ).update(last_read_at=now)
        if not updated:
            return None
        other_ids = list(
            ConversationParticipant.objects.filter(conversation_id=conversation_id)
            .exclude(user=self.user)
            .values_list("user_id", flat=True)
        )
        return other_ids, now
