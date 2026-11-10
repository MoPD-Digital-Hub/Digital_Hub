import logging

from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from project.responses import failure, success
from users.api.docs import token_refresh_schema

LOGGER = logging.getLogger(__name__)


class CustomTokenRefreshView(TokenRefreshView):
    @token_refresh_schema
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            if serializer.is_valid():
                return success(request, serializer.validated_data, message="TOKEN_REFRESHED")
            return failure(request, "INVALID_TOKEN", status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
        except TokenError as exc:
            # An expired, blacklisted or malformed refresh token: the client must sign in again.
            return failure(request, "INVALID_TOKEN", status.HTTP_401_UNAUTHORIZED, code="token_not_valid",
                           error_message=str(exc))
        except Exception:
            LOGGER.exception("Token refresh failed")
            return failure(request, "EXCEPTION_OCCURRED", status.HTTP_500_INTERNAL_SERVER_ERROR)
