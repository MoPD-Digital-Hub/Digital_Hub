from django.urls import path

from users.api.views import ministries, password_login, reset_password, user

urlpatterns = [
    path('', user),
    path('ministries/', ministries, name='user-ministries'),
    path('auth/password-login/', password_login, name='password-login'),
    path('reset-password/', reset_password),
]
