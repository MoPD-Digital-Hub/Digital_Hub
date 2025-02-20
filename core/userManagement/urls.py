from django.urls import path, include
from .views import user, reset_password

urlpatterns = [
    path('', user),
    path('reset-password/', reset_password)
]