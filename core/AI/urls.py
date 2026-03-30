from django.urls import path

from AI.api import answer, chat_history, chat_instance_detail, chat_instances, dependency_health, health
from .views import room
    
urlpatterns = [
    path("chat-new/<str:room_name>/", room, name="ai-chat-room"),
    path("health/", health, name="ai-health"),
    path("health/dependencies/", dependency_health, name="ai-dependency-health"),
    path("", chat_instances, name="ai-chat"),
    path("answer/<int:chat_instance_id>/", answer, name="ai-answer"),
    path("history/<int:chat_instance_id>/", chat_history, name="ai-history"),
    path("instance/<int:chat_instance_id>/", chat_instance_detail, name="ai-instance-detail"),
    path("delete/<int:chat_instance_id>/", chat_instance_detail, name="ai-delete"),
]
