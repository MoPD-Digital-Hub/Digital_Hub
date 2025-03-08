from django.urls import path
from mobile.api.api import app

urlpatterns = [
    path('', app),
]