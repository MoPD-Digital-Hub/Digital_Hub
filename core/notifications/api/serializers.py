from rest_framework import serializers

from notifications.models import Notification, NotificationCategory


class NotificationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCategory
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    category = NotificationCategorySerializer()
    class Meta:
        model = Notification
        fields = '__all__'