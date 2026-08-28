from django.contrib import admin
from .models import *

admin.site.register(NotificationCategory)
admin.site.register(Notification)


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'last_seen_at']
    list_filter = ['platform']
    raw_id_fields = ['user']
