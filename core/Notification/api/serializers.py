from rest_framework import serializers
from Notification.models import NotificationCategory, Notification

class NotificationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCategory
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    category = NotificationCategorySerializer()
    class Meta:
        model = Notification
        fields = '__all__'