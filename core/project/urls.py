from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from userManagement.api.api import CustomTokenRefreshView
from userManagement.oidc_views import admin_logout_view
import os
from pathlib import Path
from mobile.views import privacy_policy, vr_dashboard

BASE_DIR = Path(__file__).resolve().parent.parent.parent

urlpatterns = [
    path('admin/logout/', admin_logout_view, name='admin_logout'),
    path('admin/', admin.site.urls),
    path('privacy_policy/' , privacy_policy , name='privacy_policy' ),
    path('dashboard/vr/', vr_dashboard, name='vr_dashboard'),
    path('api/user/', include('userManagement.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/video/', include('Videos.urls')),
    path('api/mobile/', include('mobile.urls')),
    path('api/auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/ai-chat/', include('AI.urls')),
    path('api/notification/', include('Notification.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('oidc/', include('mozilla_django_oidc.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
