import logging

from celery import shared_task

LOGGER = logging.getLogger("chat.tasks")

PUSH_BODY_PREVIEW_LENGTH = 120


@shared_task
def send_chat_push(message_id):
    """Push-notify recipients of a chat message, skipping anyone who is
    muted or currently focused on the conversation (see chat.presence)."""
    from chat.models import ConversationParticipant, Message
    from chat.presence import is_focused
    from Notification.tasks.push_notification_task import send_push_to_user

    message = (
        Message.objects.select_related("sender", "conversation")
        .filter(id=message_id, is_deleted=False)
        .first()
    )
    if message is None:
        return 0

    sender = message.sender
    sender_name = (sender.get_full_name() if sender else "") or "New message"
    preview = message.body.strip()[:PUSH_BODY_PREVIEW_LENGTH] or "Sent an attachment"
    if message.conversation.type == "group":
        # "Team Alpha" / "Abebe: See you then"
        title = message.conversation.title or sender_name
        body = f"{sender_name}: {preview}"
    else:
        title = sender_name
        body = preview

    recipients = (
        ConversationParticipant.objects.filter(conversation=message.conversation)
        .exclude(user=message.sender)
        .select_related("user")
    )

    sent = 0
    for participant in recipients:
        if participant.is_muted:
            continue
        if is_focused(participant.user_id, message.conversation_id):
            continue
        sent += send_push_to_user(
            participant.user_id,
            title=title,
            body=body,
            data={
                "route": "/chat",
                "conversation_id": str(message.conversation_id),
                "message_id": str(message.id),
                "sender_id": str(message.sender_id or ""),
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            },
        )
    return sent
