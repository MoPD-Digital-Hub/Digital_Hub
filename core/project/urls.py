from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dotenv import load_dotenv
from userManagement.api.api import CustomTokenRefreshView
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(os.path.join(BASE_DIR.parent, '.env'))

is_dev = os.getenv('DEBUG_DEV')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/user/', include('userManagement.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/video/', include('Videos.urls')),
    path('api/auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if is_dev == 'True':
    urlpatterns+=[path('api/ai-chat/', include('AI.urls'))]
