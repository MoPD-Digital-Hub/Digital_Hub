from django.conf import settings
from django.db import models


class Conversation(models.Model):
    DIRECT = "direct"
    GROUP = "group"
    TYPE_CHOICES = [
        (DIRECT, "Direct"),
        (GROUP, "Group"),
    ]

    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=DIRECT)
    direct_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Deterministic '<min_user_id>:<max_user_id>' key so a direct conversation between two users is unique.",
    )
    title = models.CharField(max_length=100, null=True, blank=True, help_text="Group conversations only.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation {self.id} ({self.type})"

    @staticmethod
    def build_direct_key(user_a_id, user_b_id):
        low, high = sorted([int(user_a_id), int(user_b_id)])
        return f"{low}:{high}"


class ConversationParticipant(models.Model):
    ADMIN = "admin"
    MEMBER = "member"
    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (MEMBER, "Member"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_participations')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['conversation', 'user'], name='unique_conversation_participant'),
        ]

    def __str__(self):
        return f"{self.user} in conversation {self.conversation_id}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='sent_chat_messages',
    )
    body = models.TextField(blank=True)
    attachment = models.FileField(upload_to='chat/attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message {self.id} in conversation {self.conversation_id}"
