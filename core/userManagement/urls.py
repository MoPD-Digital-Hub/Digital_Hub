from django.urls import path, include
from .views import user, reset_password, generate_login_opt, validate_login_opt, ministries

urlpatterns = [
    path('', user),
    path('ministries/', ministries, name='user-ministries'),
    path('auth/login/',generate_login_opt ),
    path('auth/verify-otp/',validate_login_opt ),
    path('reset-password/', reset_password)
]