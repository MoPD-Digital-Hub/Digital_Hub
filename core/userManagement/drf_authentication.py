import logging

from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework.exceptions import AuthenticationFailed


LOGGER = logging.getLogger(__name__)


class OptionalOIDCAuthentication(OIDCAuthentication):
    """
    Let DRF fall through to the next auth backend when OIDC auth fails.
    This prevents non-Keycloak bearer tokens from blocking SimpleJWT auth.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed as exc:
            LOGGER.debug("Skipping OIDC auth and trying next backend: %s", str(exc))
            return None
