from django.urls import path, include
from AI.api.api import chat, get_answer

urlpatterns = [
    path('<int:chat_id>', chat),
    path('answer/<int:chat_id>', get_answer),
]