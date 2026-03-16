from django.urls import path, include
from AI.api.api import (
    answer,
    chat,
    delete_chat_instance,
    dependency_health,
    dependency_health_item,
    get_chat_list,
    health,
    ingestion_report,
    retriever_debug,
    task_status,
    tts_prefetch,
    translate,
    tts,
    update_chat_instance,
)
from .views import room
    
urlpatterns = [
    path("chat-new/<str:room_name>/", room, name="ai-chat-room"),
    path("health/", health, name="ai-health"),
    path("health/dependencies/", dependency_health, name="ai-dependency-health"),
    path("health/dependencies/<str:dependency_name>/", dependency_health_item, name="ai-dependency-health-item"),
    path("ingestion-report/", ingestion_report, name="ai-ingestion-report"),
    path("retriever-debug/", retriever_debug, name="ai-retriever-debug"),
    path("task-status/<str:task_id>/", task_status, name="ai-task-status"),
    path("tts/", tts, name="ai-tts"),
    path("tts/prefetch/", tts_prefetch, name="ai-tts-prefetch"),
    path("translate/", translate, name="ai-translate"),
    path("", chat, name="ai-chat"),
    path("answer/<int:chat_instance_id>/", answer, name="ai-answer"),
    path("history/<int:chat_instance_id>/", get_chat_list, name="ai-history"),
    path("instance/<int:chat_instance_id>/", update_chat_instance, name="ai-instance-update"),
    path("delete/<int:chat_instance_id>/", delete_chat_instance, name="ai-delete"),
]
