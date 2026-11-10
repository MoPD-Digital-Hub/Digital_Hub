from django.urls import path

from notifications.api.views import categories, devices, notifications

urlpatterns = [
    path('', notifications, name='notifications'),
    path('categories', categories, name='notification-categories'),
    path('devices', devices, name='notification-devices'),
]
