from rest_framework import serializers

from AI.models import ChatInstance, QuestionHistory


class ChatInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatInstance
        fields = ["id", "title", "created_at"]


class QuestionHistorySerializer(serializers.ModelSerializer):
    charts = serializers.SerializerMethodField()
    tool_data = serializers.SerializerMethodField()

    class Meta:
        model = QuestionHistory
        fields = ["id", "question", "response", "charts", "tool_data", "created_at", "response_at"]

    def get_charts(self, obj):
        return list(obj.chart_data or [])

    def get_tool_data(self, obj):
        return dict(obj.tool_data or {})
