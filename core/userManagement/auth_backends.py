import logging

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


LOGGER = logging.getLogger(__name__)


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    OIDC backend for TSMS:
    - Authenticates only existing users (no auto-create)
    - Matches by email first, then preferred_username -> username
    - Uses default mozilla_django_oidc token verification/settings
    """

    def filter_users_by_claims(self, claims):
        email = claims.get("email")
        preferred_username = claims.get("preferred_username")

        if email:
            users = self.UserModel.objects.filter(email__iexact=email)
            if users.exists():
                return users

        if preferred_username:
            users = self.UserModel.objects.filter(username__iexact=preferred_username)
            if users.exists():
                return users

        return self.UserModel.objects.none()

    def get_or_create_user(self, access_token, id_token, payload):
        user_info = self.get_userinfo(access_token, id_token, payload)

        if not self.verify_claims(user_info):
            LOGGER.warning("OIDC claims verification failed for %s", user_info.get("email"))
            return None

        users = self.filter_users_by_claims(user_info)

        if len(users) == 1:
            return self.update_user(users[0], user_info)

        if len(users) > 1:
            LOGGER.warning("Multiple users matched OIDC claims for %s", user_info.get("email"))
            return None

        identifier = (
            user_info.get("email")
            or user_info.get("preferred_username")
            or user_info.get("sub", "unknown")
        )
        msg = f"User not found in Time Series system: {identifier}"
        if getattr(self, "request", None):
            self.request.session["oidc_user_not_found"] = identifier
        print(msg)
        LOGGER.warning(msg)
        return None
