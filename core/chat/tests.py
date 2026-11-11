from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from chat.middleware import JWTAuthMiddleware
from chat.models import Conversation, ConversationParticipant, Message
from chat.routing import websocket_urlpatterns
from chat.services import user_group_name
from chat.tasks import send_chat_push

IN_MEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
User = get_user_model()


def make_user(name, **extra):
    return User.objects.create_user(username=name, email=f"{name}@example.test", password="Str0ng!pass",
                                    first_name=name.title(), **extra)


def direct(a, b):
    conversation = Conversation.objects.create(type=Conversation.DIRECT,
                                               direct_key=Conversation.build_direct_key(a.id, b.id))
    ConversationParticipant.objects.bulk_create([ConversationParticipant(conversation=conversation, user=u) for u in (a, b)])
    return conversation


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ConversationApiTests(TestCase):
    def setUp(self):
        self.abebe, self.sara, self.outsider = make_user("abebe"), make_user("sara"), make_user("outsider")
        self.api = APIClient()
        self.api.force_authenticate(self.abebe)

    def post(self, path, data=None):
        return self.api.post(path, data or {}, format="json", HTTP_HOST="localhost")

    def get(self, path):
        return self.api.get(path, HTTP_HOST="localhost")

    def test_requires_sign_in(self):
        self.assertEqual(APIClient().get("/api/chat/conversations/", HTTP_HOST="localhost").status_code, 403)

    def test_starting_a_direct_conversation_twice_returns_the_same_one(self):
        first = self.post("/api/chat/conversations/", {"user_id": self.sara.id})
        again = self.post("/api/chat/conversations/", {"user_id": self.sara.id})
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertEqual(first.json()["data"]["id"], again.json()["data"]["id"])
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ConversationParticipant.objects.count(), 2)

    def test_direct_conversation_validation(self):
        cases = [({}, 400, "USER_ID_REQUIRED"), ({"user_id": "x"}, 400, "USER_ID_INVALID"),
                 ({"user_id": self.abebe.id}, 400, "SELF_CONVERSATION"), ({"user_id": 999999}, 404, "USER_NOT_FOUND")]
        for data, status, code in cases:
            response = self.post("/api/chat/conversations/", data)
            self.assertEqual((response.status_code, response.json()["error"]["code"]), (status, code))

    def test_group_creator_is_admin_and_needs_a_title_and_members(self):
        self.assertEqual(self.post("/api/chat/conversations/", {"type": "group", "user_ids": [self.sara.id]})
                         .json()["error"]["code"], "TITLE_REQUIRED")
        self.assertEqual(self.post("/api/chat/conversations/", {"type": "group", "title": "Team"})
                         .json()["error"]["code"], "USER_IDS_REQUIRED")
        response = self.post("/api/chat/conversations/", {"type": "group", "title": "Team", "user_ids": [self.sara.id]})
        self.assertEqual(response.status_code, 201)
        roles = dict(ConversationParticipant.objects.values_list("user_id", "role"))
        self.assertEqual(roles, {self.abebe.id: ConversationParticipant.ADMIN, self.sara.id: ConversationParticipant.MEMBER})

    def test_only_staff_can_create_channels(self):
        response = self.post("/api/chat/conversations/", {"type": "channel", "title": "News"})
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (403, "CHANNEL_STAFF_ONLY"))

    def test_only_members_see_a_conversation(self):
        conversation = direct(self.sara, self.outsider)
        self.assertEqual(self.get(f"/api/chat/conversations/{conversation.id}/").status_code, 404)
        self.assertEqual(self.get(f"/api/chat/conversations/{conversation.id}/messages/").status_code, 404)
        self.assertEqual(self.post(f"/api/chat/conversations/{conversation.id}/messages/", {"body": "hi"}).status_code, 404)
        self.assertEqual(self.get("/api/chat/conversations/").json()["data"], [])


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class MessageApiTests(TestCase):
    def setUp(self):
        self.abebe, self.sara = make_user("abebe"), make_user("sara")
        self.conversation = direct(self.abebe, self.sara)
        self.api = APIClient()
        self.api.force_authenticate(self.abebe)
        self.url = f"/api/chat/conversations/{self.conversation.id}/messages/"

    def send(self, body):
        with patch("chat.api.views.send_chat_push") as push, patch("chat.api.views.broadcast_to_users") as broadcast:
            response = self.api.post(self.url, {"body": body}, format="json", HTTP_HOST="localhost")
        return response, push, broadcast

    def test_sending_stores_broadcasts_and_queues_a_push(self):
        response, push, broadcast = self.send("  Selam  ")
        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual((message.body, message.sender), ("Selam", self.abebe))
        push.delay.assert_called_once_with(message.id)
        user_ids, payload = broadcast.call_args.args
        self.assertEqual(sorted(user_ids), sorted([self.abebe.id, self.sara.id]))
        self.assertEqual((payload["type"], payload["conversation_id"], payload["message"]["body"]),
                         ("message.new", self.conversation.id, "Selam"))
        membership = ConversationParticipant.objects.get(conversation=self.conversation, user=self.abebe)
        self.assertEqual(membership.last_read_at, message.created_at)

    def test_empty_message_is_rejected(self):
        response, push, _ = self.send("   ")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (400, "EMPTY_MESSAGE"))
        push.delay.assert_not_called()

    def test_messages_page_newest_first(self):
        ids = [Message.objects.create(conversation=self.conversation, sender=self.sara, body=str(i)).id for i in range(5)]
        Message.objects.create(conversation=self.conversation, sender=self.sara, body="gone", is_deleted=True)
        page = self.api.get(self.url + "?limit=2", HTTP_HOST="localhost").json()["data"]
        self.assertEqual([m["id"] for m in page["messages"]], [ids[4], ids[3]])
        self.assertEqual((page["has_more"], page["next_before"]), (True, ids[3]))
        rest = self.api.get(self.url + f"?limit=10&before={ids[3]}", HTTP_HOST="localhost").json()["data"]
        self.assertEqual([m["id"] for m in rest["messages"]], [ids[2], ids[1], ids[0]])
        self.assertFalse(rest["has_more"])

    def test_members_cannot_post_in_a_channel(self):
        channel = Conversation.objects.create(type=Conversation.CHANNEL, title="News", created_by=self.sara)
        ConversationParticipant.objects.create(conversation=channel, user=self.sara, role=ConversationParticipant.ADMIN)
        ConversationParticipant.objects.create(conversation=channel, user=self.abebe)
        response = self.api.post(f"/api/chat/conversations/{channel.id}/messages/", {"body": "hi"}, format="json",
                                 HTTP_HOST="localhost")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (403, "READ_ONLY_CHANNEL"))


class PushTaskTests(TestCase):
    def setUp(self):
        self.abebe, self.sara, self.kebede = make_user("abebe"), make_user("sara"), make_user("kebede")
        self.group = Conversation.objects.create(type=Conversation.GROUP, title="Team Alpha", created_by=self.abebe)
        for user in (self.abebe, self.sara, self.kebede):
            ConversationParticipant.objects.create(conversation=self.group, user=user)

    def run_task(self, message, focused=()):
        with patch("notifications.tasks.send_push_to_user", return_value=1) as push, \
                patch("chat.presence.is_focused", side_effect=lambda user_id, _conv: user_id in focused):
            sent = send_chat_push(message.id)
        return sent, push

    def test_everyone_but_the_sender_is_notified(self):
        message = Message.objects.create(conversation=self.group, sender=self.abebe, body="See you then")
        sent, push = self.run_task(message)
        self.assertEqual(sent, 2)
        self.assertEqual(sorted(call.args[0] for call in push.call_args_list), sorted([self.sara.id, self.kebede.id]))
        self.assertEqual(push.call_args.kwargs["title"], "Team Alpha")
        self.assertEqual(push.call_args.kwargs["body"], "Abebe: See you then")
        self.assertEqual(push.call_args.kwargs["data"]["conversation_id"], str(self.group.id))

    def test_muted_and_focused_members_are_skipped(self):
        ConversationParticipant.objects.filter(conversation=self.group, user=self.sara).update(is_muted=True)
        message = Message.objects.create(conversation=self.group, sender=self.abebe, body="hi")
        sent, push = self.run_task(message, focused={self.kebede.id})
        self.assertEqual(sent, 0)
        push.assert_not_called()

    def test_deleted_or_missing_message_sends_nothing(self):
        message = Message.objects.create(conversation=self.group, sender=self.abebe, body="hi", is_deleted=True)
        self.assertEqual(self.run_task(message)[0], 0)
        self.assertEqual(send_chat_push(999999), 0)


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class SocketTests(TransactionTestCase):
    """/ws/dm/: one socket per user, authenticated by a JWT access token."""

    application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

    def test_a_signed_in_user_receives_their_events(self):
        async def scenario():
            user = await database_sync_to_async(make_user)("abebe")
            token = str(RefreshToken.for_user(user).access_token)
            socket = WebsocketCommunicator(self.application, f"/ws/dm/?token={token}")
            connected, _ = await socket.connect()
            payload = {"type": "message.new", "conversation_id": 7, "message": {"body": "Selam"}}
            await get_channel_layer().group_send(user_group_name(user.id), {"type": "chat.event", "payload": payload})
            received = await socket.receive_json_from()
            await socket.disconnect()
            return connected, received, payload

        connected, received, payload = async_to_sync(scenario)()
        self.assertTrue(connected)
        self.assertEqual(received, payload)

    def test_a_missing_or_bad_token_is_closed_with_4401(self):
        async def scenario(path):
            socket = WebsocketCommunicator(self.application, path)
            await socket.connect()
            closed = await socket.receive_output()
            return closed

        for path in ("/ws/dm/", "/ws/dm/?token=not-a-token"):
            closed = async_to_sync(scenario)(path)
            self.assertEqual((closed["type"], closed["code"]), ("websocket.close", 4401), path)
