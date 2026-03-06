from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed
from requests.exceptions import MissingSchema

from userManagement.drf_authentication import OptionalOIDCAuthentication


class OptionalOIDCAuthenticationTests(TestCase):
    @patch("mozilla_django_oidc.contrib.drf.OIDCAuthentication.authenticate", side_effect=MissingSchema("bad url"))
    def test_oidc_missing_schema_falls_through(self, _mock):
        auth = OptionalOIDCAuthentication()
        result = auth.authenticate(request=object())
        self.assertIsNone(result)

    @patch("mozilla_django_oidc.contrib.drf.OIDCAuthentication.authenticate", side_effect=AuthenticationFailed("nope"))
    def test_oidc_auth_failed_falls_through(self, _mock):
        auth = OptionalOIDCAuthentication()
        result = auth.authenticate(request=object())
        self.assertIsNone(result)
