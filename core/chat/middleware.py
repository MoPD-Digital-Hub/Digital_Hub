import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.security.websocket import OriginValidator
from django.conf import settings

LOGGER = logging.getLogger("chat.middleware")


class MobileFriendlyOriginValidator(OriginValidator):
    """Browser connections must present an Origin allowed by ALLOWED_HOSTS,
    but native clients (the Flutter app) send no Origin header at all —
    allow those instead of rejecting the handshake with a 403."""

    def __init__(self, application):
        allowed_hosts = settings.ALLOWED_HOSTS
        if settings.DEBUG and not allowed_hosts:
            allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
        super().__init__(application, allowed_hosts)

    def valid_origin(self, parsed_origin):
        if parsed_origin is None:
            return True
        return super().valid_origin(parsed_origin)


@database_sync_to_async
def _get_user_for_token(raw_token):
    from rest_framework_simplejwt.authentication import JWTAuthentication

    authenticator = JWTAuthentication()
    validated = authenticator.get_validated_token(raw_token)
    return authenticator.get_user(validated)


class JWTAuthMiddleware:
    """Populate scope['user'] from a SimpleJWT access token.

    The token is read from the `token` query parameter, or from the
    Sec-WebSocket-Protocol header as the pair ("bearer", "<token>") for
    clients that can't set query strings safely. An invalid or missing token
    leaves the user anonymous; consumers decide whether to close.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        scope["user"] = AnonymousUser()
        token = self._token_from_scope(scope)
        if token:
            try:
                scope["user"] = await _get_user_for_token(token)
            except Exception:
                LOGGER.info("Rejected websocket token", exc_info=True)
        return await self.inner(scope, receive, send)

    @staticmethod
    def _token_from_scope(scope):
        query = parse_qs(scope.get("query_string", b"").decode())
        token_values = query.get("token")
        if token_values:
            return token_values[0]

        subprotocols = scope.get("subprotocols") or []
        if len(subprotocols) >= 2 and subprotocols[0].lower() == "bearer":
            return subprotocols[1]
        return None
