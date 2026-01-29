from django.urls import path, include
from AI.api.api import chat, get_chat_list, delete_chat_instance
from .views import room

urlpatterns = [
    path("chat-new/<str:room_name>/", room),
    path('', chat),
    path('history/<int:chat_instance_id>/', get_chat_list),
    path('delete/<int:chat_instance_id>/', delete_chat_instance),
]