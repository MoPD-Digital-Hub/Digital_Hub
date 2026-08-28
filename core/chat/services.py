from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def user_group_name(user_id):
    return f"chat_user_{user_id}"


def broadcast_to_users(user_ids, payload):
    """Send a chat event payload to each user's personal websocket group."""
    channel_layer = get_channel_layer()
    for user_id in user_ids:
        async_to_sync(channel_layer.group_send)(
            user_group_name(user_id),
            {"type": "chat.event", "payload": payload},
        )


def conversation_user_ids(conversation):
    return list(conversation.participants.values_list("user_id", flat=True))
