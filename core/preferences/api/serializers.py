from rest_framework import serializers

from preferences.models import SECTIONS, Follow, UserPreference


class SectionSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=SECTIONS)
    visible = serializers.BooleanField(default=True)


class PreferenceSerializer(serializers.ModelSerializer):
    # A list field, not a nested serializer: the whole list is stored as one JSON value.
    sections = serializers.ListField(child=SectionSerializer(), required=False)
    movers_limit = serializers.IntegerField(min_value=1, max_value=20, required=False)

    class Meta:
        model = UserPreference
        fields = ("sections", "period", "movers_direction", "movers_scope", "movers_limit", "language", "updated_at")
        read_only_fields = ("updated_at",)

    def validate_sections(self, value):
        keys = [entry["key"] for entry in value]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("Each section may appear once.")
        # A partial update skips field defaults, so `visible` may be absent here.
        return [{"key": entry["key"], "visible": entry.get("visible", True)} for entry in value]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Always the full list, so a client can render settings without knowing the defaults.
        data["sections"] = instance.ordered_sections()
        return data


class FollowSerializer(serializers.ModelSerializer):
    """`id` is the item's id in its own service; `follow_id` is this record."""

    follow_id = serializers.IntegerField(source="pk", read_only=True)
    id = serializers.CharField(source="external_id", read_only=True)

    class Meta:
        model = Follow
        fields = ("follow_id", "kind", "id", "organization_id", "name", "name_am", "code", "position", "created_at")


class FollowCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Follow.KIND_CHOICES)
    id = serializers.CharField(max_length=64)
    organization_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class FollowOrderSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Follow.KIND_CHOICES)
    follow_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
