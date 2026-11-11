from django.contrib import admin

from .models import Follow, UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "period", "movers_direction", "movers_scope", "language", "updated_at")
    list_filter = ("period", "language")
    search_fields = ("user__email",)
    raw_id_fields = ("user",)


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "name", "external_id", "organization_id", "position", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__email", "name", "code", "external_id")
    raw_id_fields = ("user",)
