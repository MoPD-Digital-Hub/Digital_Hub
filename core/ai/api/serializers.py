from rest_framework import serializers

from ai.models import ChatInstance, QuestionHistory


class ChatInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatInstance
        fields = '__all__'


class QuestionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionHistory
        fields = '__all__'