from django.contrib import admin
from .models import *

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'file', 'is_loaded')
    list_filter = ('is_loaded',)
    search_fields = ('name',)
    ordering = ('id',)


@admin.register(LoadedFile)
class LoadedFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'number')
    ordering = ('id',)


@admin.register(ChatInstance)
class ChatInstanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('title', 'user__username', 'user__email')
    ordering = ('-created_at',)


@admin.register(QuestionHistory)
class QuestionHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'question',
        'instance',
        'created_at',
        'response_at',
    )
    search_fields = ('question', 'response')
    list_filter = (
        'created_at',
        'response_at',
        'instance__user',
    )
    ordering = ('-created_at',)