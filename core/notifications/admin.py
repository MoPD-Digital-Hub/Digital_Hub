from django.contrib import admin

from .models import DeviceToken, Notification, NotificationCategory

admin.site.register(NotificationCategory)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "is_active", "send_at", "sent_at"]
    list_filter = ["is_active", "category"]
    search_fields = ["title", "message"]
    readonly_fields = ["sent_at"]


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'last_seen_at']
    list_filter = ['platform']
    raw_id_fields = ['user']
