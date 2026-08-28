from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Q

from chat.models import Conversation, ConversationParticipant, Message
from chat.services import broadcast_to_users, conversation_user_ids
from chat.tasks import send_chat_push
from userManagement.models import CustomUser
from .serializers import ChatUserSerializer, ConversationSerializer, MessageSerializer

MESSAGES_PAGE_SIZE_DEFAULT = 30
MESSAGES_PAGE_SIZE_MAX = 100
GROUP_MEMBERS_MAX = 100


def _request_id(request):
    return getattr(request, "request_id", None)


def _ok(request, data=None, message="SUCCESS", status_code=status.HTTP_200_OK):
    return Response(
        {
            "result": "SUCCESS",
            "message": message,
            "request_id": _request_id(request),
            "data": data,
        },
        status=status_code,
    )


def _err(request, code, message, status_code, details=None):
    return Response(
        {
            "result": "FAILURE",
            "message": code,
            "request_id": _request_id(request),
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "data": None,
        },
        status=status_code,
    )


def _get_membership(request, conversation_id):
    """Returns the requesting user's participant row, or None. All
    conversation access must go through this membership check."""
    return (
        ConversationParticipant.objects.select_related("conversation")
        .filter(conversation_id=conversation_id, user=request.user)
        .first()
    )


def _conversation_queryset(user):
    return (
        Conversation.objects.filter(participants__user=user)
        .prefetch_related("participants__user")
        .order_by("-updated_at")
    )


def _serialize_for(request, conversation_id):
    conversation = _conversation_queryset(request.user).get(id=conversation_id)
    return ConversationSerializer(conversation, context={"request": request}).data


def _notify_conversation_updated(conversation, action, user_ids=None, extra=None):
    """Tell every affected user's socket that a conversation changed shape
    (created, renamed, membership change) so clients refetch it."""
    payload = {
        "type": "conversation.updated",
        "conversation_id": conversation.id,
        "action": action,
    }
    if extra:
        payload.update(extra)
    if user_ids is None:
        user_ids = conversation_user_ids(conversation)
    broadcast_to_users(user_ids, payload)


def _parse_user_ids(raw):
    """Returns (list_of_ids, error_code). Accepts a JSON list of ints."""
    if not isinstance(raw, list) or not raw:
        return None, "USER_IDS_REQUIRED"
    try:
        user_ids = sorted({int(user_id) for user_id in raw})
    except (TypeError, ValueError):
        return None, "USER_IDS_INVALID"
    return user_ids, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_users(request):
    """Users the requester can start a conversation with. Optional
    ?search= filters by name or email."""
    queryset = CustomUser.objects.filter(is_active=True).exclude(id=request.user.id)

    search = request.query_params.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )

    queryset = queryset.order_by('first_name', 'last_name')
    serializer = ChatUserSerializer(queryset, many=True, context={"request": request})
    return _ok(request, serializer.data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def conversations(request):
    if request.method == 'GET':
        queryset = _conversation_queryset(request.user)
        serializer = ConversationSerializer(queryset, many=True, context={"request": request})
        return _ok(request, serializer.data)

    if request.data.get('type') == Conversation.GROUP:
        return _create_group(request)

    user_id = request.data.get('user_id')
    if not user_id:
        return _err(request, "USER_ID_REQUIRED", "user_id is required.", status.HTTP_400_BAD_REQUEST)

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _err(request, "USER_ID_INVALID", "user_id must be an integer.", status.HTTP_400_BAD_REQUEST)

    if user_id == request.user.id:
        return _err(request, "SELF_CONVERSATION", "Cannot start a conversation with yourself.", status.HTTP_400_BAD_REQUEST)

    other_user = CustomUser.objects.filter(id=user_id, is_active=True).first()
    if other_user is None:
        return _err(request, "USER_NOT_FOUND", "User doesn't exist!", status.HTTP_404_NOT_FOUND)

    direct_key = Conversation.build_direct_key(request.user.id, other_user.id)
    try:
        with transaction.atomic():
            conversation, created = Conversation.objects.get_or_create(
                direct_key=direct_key,
                defaults={"type": Conversation.DIRECT},
            )
            if created:
                ConversationParticipant.objects.bulk_create([
                    ConversationParticipant(conversation=conversation, user=request.user),
                    ConversationParticipant(conversation=conversation, user=other_user),
                ])
    except IntegrityError:
        conversation = Conversation.objects.get(direct_key=direct_key)
        created = False

    return _ok(
        request,
        _serialize_for(request, conversation.id),
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


def _create_group(request):
    title = str(request.data.get('title', '')).strip()
    if not title:
        return _err(request, "TITLE_REQUIRED", "Group conversations need a title.", status.HTTP_400_BAD_REQUEST)

    user_ids, error = _parse_user_ids(request.data.get('user_ids'))
    if error:
        return _err(request, error, "user_ids must be a non-empty list of user ids.", status.HTTP_400_BAD_REQUEST)

    user_ids = [user_id for user_id in user_ids if user_id != request.user.id]
    if not user_ids:
        return _err(request, "USER_IDS_REQUIRED", "A group needs at least one other member.", status.HTTP_400_BAD_REQUEST)
    if len(user_ids) > GROUP_MEMBERS_MAX:
        return _err(request, "TOO_MANY_MEMBERS", f"A group can have at most {GROUP_MEMBERS_MAX} members.", status.HTTP_400_BAD_REQUEST)

    members = list(CustomUser.objects.filter(id__in=user_ids, is_active=True))
    missing = set(user_ids) - {member.id for member in members}
    if missing:
        return _err(
            request, "USER_NOT_FOUND", "Some users don't exist.",
            status.HTTP_404_NOT_FOUND, details={"user_ids": sorted(missing)},
        )

    with transaction.atomic():
        conversation = Conversation.objects.create(
            type=Conversation.GROUP, title=title, created_by=request.user,
        )
        ConversationParticipant.objects.bulk_create(
            [ConversationParticipant(conversation=conversation, user=request.user, role=ConversationParticipant.ADMIN)]
            + [ConversationParticipant(conversation=conversation, user=member) for member in members]
        )

    _notify_conversation_updated(conversation, "created")
    return _ok(request, _serialize_for(request, conversation.id), status_code=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, conversation_id):
    membership = _get_membership(request, conversation_id)
    if membership is None:
        return _err(request, "CONVERSATION_NOT_FOUND", "Conversation doesn't exist!", status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return _ok(request, _serialize_for(request, conversation_id))

    conversation = membership.conversation
    if conversation.type != Conversation.GROUP:
        return _err(request, "NOT_GROUP", "Only group conversations can be renamed.", status.HTTP_400_BAD_REQUEST)
    if membership.role != ConversationParticipant.ADMIN:
        return _err(request, "NOT_ADMIN", "Only group admins can rename the group.", status.HTTP_403_FORBIDDEN)

    title = str(request.data.get('title', '')).strip()
    if not title:
        return _err(request, "TITLE_REQUIRED", "title is required.", status.HTTP_400_BAD_REQUEST)

    conversation.title = title
    conversation.save(update_fields=["title", "updated_at"])
    _notify_conversation_updated(conversation, "renamed", extra={"title": title})
    return _ok(request, _serialize_for(request, conversation_id))


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def conversation_participants(request, conversation_id):
    membership = _get_membership(request, conversation_id)
    if membership is None:
        return _err(request, "CONVERSATION_NOT_FOUND", "Conversation doesn't exist!", status.HTTP_404_NOT_FOUND)

    conversation = membership.conversation
    if conversation.type != Conversation.GROUP:
        return _err(request, "NOT_GROUP", "Members can only be managed on group conversations.", status.HTTP_400_BAD_REQUEST)

    is_admin = membership.role == ConversationParticipant.ADMIN

    if request.method == 'POST':
        if not is_admin:
            return _err(request, "NOT_ADMIN", "Only group admins can add members.", status.HTTP_403_FORBIDDEN)

        user_ids, error = _parse_user_ids(request.data.get('user_ids'))
        if error:
            return _err(request, error, "user_ids must be a non-empty list of user ids.", status.HTTP_400_BAD_REQUEST)

        members = list(CustomUser.objects.filter(id__in=user_ids, is_active=True))
        missing = set(user_ids) - {member.id for member in members}
        if missing:
            return _err(
                request, "USER_NOT_FOUND", "Some users don't exist.",
                status.HTTP_404_NOT_FOUND, details={"user_ids": sorted(missing)},
            )

        existing_ids = set(conversation.participants.values_list("user_id", flat=True))
        new_members = [member for member in members if member.id not in existing_ids]
        if len(existing_ids) + len(new_members) > GROUP_MEMBERS_MAX:
            return _err(request, "TOO_MANY_MEMBERS", f"A group can have at most {GROUP_MEMBERS_MAX} members.", status.HTTP_400_BAD_REQUEST)

        added = []
        for member in new_members:
            _, created = ConversationParticipant.objects.get_or_create(
                conversation=conversation, user=member,
            )
            if created:
                added.append(member.id)

        if added:
            conversation.save(update_fields=["updated_at"])
            _notify_conversation_updated(conversation, "members_added", extra={"user_ids": added})
        return _ok(request, _serialize_for(request, conversation_id))

    # DELETE: remove a member (admin) or leave (self)
    try:
        target_id = int(request.data.get('user_id'))
    except (TypeError, ValueError):
        return _err(request, "USER_ID_INVALID", "user_id must be an integer.", status.HTTP_400_BAD_REQUEST)

    leaving = target_id == request.user.id
    if not leaving and not is_admin:
        return _err(request, "NOT_ADMIN", "Only group admins can remove members.", status.HTTP_403_FORBIDDEN)

    target = ConversationParticipant.objects.filter(conversation=conversation, user_id=target_id).first()
    if target is None:
        return _err(request, "PARTICIPANT_NOT_FOUND", "That user is not in this group.", status.HTTP_404_NOT_FOUND)

    # Notify everyone including the removed user, then delete.
    affected_ids = conversation_user_ids(conversation)
    target.delete()

    # Never leave a group without an admin: promote the oldest member.
    remaining = ConversationParticipant.objects.filter(conversation=conversation)
    if remaining.exists() and not remaining.filter(role=ConversationParticipant.ADMIN).exists():
        oldest = remaining.order_by("joined_at").first()
        oldest.role = ConversationParticipant.ADMIN
        oldest.save(update_fields=["role"])

    conversation.save(update_fields=["updated_at"])
    _notify_conversation_updated(
        conversation,
        "member_left" if leaving else "member_removed",
        user_ids=affected_ids,
        extra={"user_id": target_id},
    )

    if leaving:
        return _ok(request, None, message="LEFT_GROUP")
    return _ok(request, _serialize_for(request, conversation_id))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def conversation_messages(request, conversation_id):
    membership = _get_membership(request, conversation_id)
    if membership is None:
        return _err(request, "CONVERSATION_NOT_FOUND", "Conversation doesn't exist!", status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        try:
            limit = min(int(request.query_params.get('limit', MESSAGES_PAGE_SIZE_DEFAULT)), MESSAGES_PAGE_SIZE_MAX)
        except (TypeError, ValueError):
            limit = MESSAGES_PAGE_SIZE_DEFAULT

        queryset = Message.objects.filter(
            conversation_id=conversation_id, is_deleted=False
        ).select_related("sender").order_by('-id')

        before = request.query_params.get('before')
        if before:
            try:
                queryset = queryset.filter(id__lt=int(before))
            except (TypeError, ValueError):
                return _err(request, "BEFORE_INVALID", "before must be a message id.", status.HTTP_400_BAD_REQUEST)

        messages = list(queryset[:limit + 1])
        has_more = len(messages) > limit
        messages = messages[:limit]
        serializer = MessageSerializer(messages, many=True, context={"request": request})
        return _ok(
            request,
            {
                "messages": serializer.data,
                "has_more": has_more,
                "next_before": messages[-1].id if has_more and messages else None,
            },
        )

    body = str(request.data.get('body', '')).strip()
    attachment = request.FILES.get('attachment')
    if not body and not attachment:
        return _err(request, "EMPTY_MESSAGE", "Message body or attachment is required.", status.HTTP_400_BAD_REQUEST)

    conversation = membership.conversation
    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=body,
        attachment=attachment,
    )
    # Sending counts as having read the conversation up to now.
    membership.last_read_at = message.created_at
    membership.save(update_fields=["last_read_at"])
    conversation.save(update_fields=["updated_at"])

    serializer = MessageSerializer(message, context={"request": request})
    broadcast_to_users(
        conversation_user_ids(conversation),
        {
            "type": "message.new",
            "conversation_id": conversation.id,
            "sender_id": request.user.id,
            "message": serializer.data,
        },
    )
    send_chat_push.delay(message.id)

    return _ok(request, serializer.data, status_code=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_conversation_read(request, conversation_id):
    membership = _get_membership(request, conversation_id)
    if membership is None:
        return _err(request, "CONVERSATION_NOT_FOUND", "Conversation doesn't exist!", status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    membership.last_read_at = now
    membership.save(update_fields=["last_read_at"])

    other_ids = [uid for uid in conversation_user_ids(membership.conversation) if uid != request.user.id]
    broadcast_to_users(
        other_ids,
        {
            "type": "message.read",
            "conversation_id": membership.conversation_id,
            "user_id": request.user.id,
            "last_read_at": now.isoformat(),
        },
    )
    return _ok(request, {"last_read_at": now.isoformat()})
