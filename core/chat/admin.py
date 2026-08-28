from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    raw_id_fields = ['user']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'title', 'direct_key', 'created_by', 'updated_at']
    list_filter = ['type']
    raw_id_fields = ['created_by']
    inlines = [ConversationParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'body', 'is_deleted', 'created_at']
    list_filter = ['is_deleted']
    search_fields = ['body']
    raw_id_fields = ['conversation', 'sender']


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'user', 'role', 'is_muted', 'last_read_at', 'joined_at']
    list_filter = ['role', 'is_muted']
    raw_id_fields = ['conversation', 'user']
