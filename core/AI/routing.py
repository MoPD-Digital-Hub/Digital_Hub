from django.urls import re_path

from . import consumers
from .v2.consumers import ChatConsumerV2

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_name>\w+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/chat-web/(?P<room_name>\w+)/$", consumers.ChatWebConsumer.as_asgi()),
    re_path(r"ws/tts-stream/$", consumers.TTSStreamConsumer.as_asgi()),
    re_path(r"ws/v2/chat/(?P<room_name>\w+)/$", ChatConsumerV2.as_asgi()),
]
