from django.urls import path
from .views import *

urlpatterns = [
    path('notifications', notifications, name='notifications'),
    path('notification-categories', categories, name='notification-categories'),
]