import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

# Initialize Django before importing anything that touches models/auth.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from AI.routing import websocket_urlpatterns as ai_websocket_urlpatterns
from chat.middleware import JWTAuthMiddleware, MobileFriendlyOriginValidator
from chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": MobileFriendlyOriginValidator(
        JWTAuthMiddleware(
            URLRouter(ai_websocket_urlpatterns + chat_websocket_urlpatterns)
        )
    ),
})
