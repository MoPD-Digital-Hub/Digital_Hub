from django.urls import path

from users.api.views import generate_login_opt, ministries, password_login, reset_password, user, validate_login_opt

urlpatterns = [
    path('', user),
    path('ministries/', ministries, name='user-ministries'),
    path('auth/login/',generate_login_opt ),
    path('auth/verify-otp/',validate_login_opt ),
    path('auth/password-login/', password_login, name='password-login'),
    path('reset-password/', reset_password)
]