from django.urls import path
from mobile.api import api

urlpatterns = [
    path('dashboard/apps/', api.app),
    path('dashboard/lastest-videos/', api.latest_videos),
]