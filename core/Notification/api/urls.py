from django.urls import path
from .views import *

urlpatterns = [
    path('', notifications, name='notifications'),
    path('categories', categories, name='notification-categories'),
    path('devices', devices, name='notification-devices'),
]