from django.urls import path

from chat.api.views import (
    chat_users,
    conversation_detail,
    conversation_messages,
    conversation_participants,
    conversations,
    mark_conversation_read,
)

urlpatterns = [
    path("users/", chat_users, name="chat-users"),
    path("conversations/", conversations, name="chat-conversations"),
    path("conversations/<int:conversation_id>/", conversation_detail, name="chat-conversation-detail"),
    path("conversations/<int:conversation_id>/participants/", conversation_participants, name="chat-participants"),
    path("conversations/<int:conversation_id>/messages/", conversation_messages, name="chat-messages"),
    path("conversations/<int:conversation_id>/read/", mark_conversation_read, name="chat-mark-read"),
]
