from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from dashboard.views import privacy_policy
from users.api.views import CustomTokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('privacy_policy/' , privacy_policy , name='privacy_policy' ),
    path('privacy-policy/', privacy_policy, name='privacy_policy_hyphen'),
    path('api/user/', include('users.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/mobile/', include('mobile.urls')),
    path('api/mobile/', include('integrations.dpmes.urls')),
    path('api/mobile/', include('integrations.time_series.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs-swagger'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='api-schema'), name='api-docs-redoc'),
    path('api/auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/ai-chat/', include('ai.urls')),
    path('api/notification/', include('notifications.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/preferences/', include('preferences.urls')),
    path('dashboard/', include('dashboard.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
