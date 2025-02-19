from django.urls import path, include
from Videos.api.api import video_api


urlpatterns = [
    path('', video_api),
]