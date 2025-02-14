from django.urls import path, include
from .views import user

urlpatterns = [
    path('', user),
]