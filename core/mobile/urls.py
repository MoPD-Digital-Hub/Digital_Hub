from django.urls import path
from mobile.api import api

urlpatterns = [
    path('dashbord/apps/', api.app),
    path('dashbord/lastest-videos/', api.latest_videos),
]