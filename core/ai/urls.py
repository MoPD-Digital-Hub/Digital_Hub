from django.urls import path

from ai.api.views import (
    answer,
    chat,
    delete_chat_instance,
    dependency_health,
    dependency_health_item,
    get_chat_list,
    health,
    task_status,
    update_chat_instance,
)
from ai.documents.views import download_document

urlpatterns = [
    path("health/", health, name="ai-health"),
    path("health/dependencies/", dependency_health, name="ai-dependency-health"),
    path("health/dependencies/<str:dependency_name>/", dependency_health_item, name="ai-dependency-health-item"),
    path("task-status/<str:task_id>/", task_status, name="ai-task-status"),
    path("", chat, name="ai-chat"),
    path("answer/<int:chat_instance_id>/", answer, name="ai-answer"),
    path("history/<int:chat_instance_id>/", get_chat_list, name="ai-history"),
    path("instance/<int:chat_instance_id>/", update_chat_instance, name="ai-instance-update"),
    path("delete/<int:chat_instance_id>/", delete_chat_instance, name="ai-delete"),
    path("documents/<uuid:document_id>/", download_document, name="ai-document"),
]
