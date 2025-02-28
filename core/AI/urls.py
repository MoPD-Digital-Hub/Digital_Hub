from django.urls import path, include
from AI.api.api import chat, get_answer, get_chat_list

urlpatterns = [
    path('', chat),
    path('history/<int:chat_instance_id>/', get_chat_list),
    path('answer/<int:chat_id>/', get_answer),
]