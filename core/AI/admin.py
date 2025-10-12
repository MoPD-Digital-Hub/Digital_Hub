from django.contrib import admin
from .models import *


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'file', 'is_loaded')  # Columns shown in the admin list view
    list_filter = ('is_loaded',)  # Sidebar filter
    search_fields = ('name',)  # Search bar for document names
    list_editable = ('is_loaded',)  # Allows toggling 'is_loaded' directly in the list view
    ordering = ('name',)  # Sort alphabetically by default


admin.site.register(LoadedFile)
admin.site.register(ChatInstance)
admin.site.register(QuestionHistory)