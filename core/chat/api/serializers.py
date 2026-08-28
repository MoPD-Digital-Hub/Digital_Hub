from rest_framework import serializers

from chat.models import Conversation, Message
from userManagement.models import CustomUser


class ChatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'email', 'photo', 'excellence']


class MessageSerializer(serializers.ModelSerializer):
    sender = ChatUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'body', 'attachment', 'created_at', 'edited_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializes a conversation from the requesting user's point of view.

    Expects the queryset to be prefetched with participants__user and
    annotated per-instance via context['request'].user.
    """

    other_participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'type', 'title', 'created_by', 'other_participants', 'last_message',
            'unread_count', 'is_muted', 'my_role', 'participant_count',
            'created_at', 'updated_at',
        ]

    def _my_participant(self, conversation):
        user = self.context['request'].user
        for participant in conversation.participants.all():
            if participant.user_id == user.id:
                return participant
        return None

    def get_other_participants(self, conversation):
        user = self.context['request'].user
        others = [p.user for p in conversation.participants.all() if p.user_id != user.id]
        return ChatUserSerializer(others, many=True, context=self.context).data

    def get_last_message(self, conversation):
        message = conversation.messages.filter(is_deleted=False).order_by('-created_at').first()
        if message is None:
            return None
        return MessageSerializer(message, context=self.context).data

    def get_unread_count(self, conversation):
        user = self.context['request'].user
        participant = self._my_participant(conversation)
        queryset = conversation.messages.filter(is_deleted=False).exclude(sender=user)
        if participant and participant.last_read_at:
            queryset = queryset.filter(created_at__gt=participant.last_read_at)
        return queryset.count()

    def get_is_muted(self, conversation):
        participant = self._my_participant(conversation)
        return bool(participant and participant.is_muted)

    def get_my_role(self, conversation):
        participant = self._my_participant(conversation)
        return participant.role if participant else None

    def get_participant_count(self, conversation):
        return len(conversation.participants.all())
