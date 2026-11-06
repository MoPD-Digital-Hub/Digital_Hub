from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
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


from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from userManagement.models import CustomUser


@override_settings(AXES_ENABLED=True)
class PasswordLoginTests(TestCase):
    url = "/api/user/auth/password-login/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            email="person@example.com",
            username="person",
            first_name="Test",
            last_name="Person",
            password="Str0ng!Pass",
        )

    @patch("userManagement.views.send_email")
    def test_valid_credentials_return_tokens_without_email(self, mock_send_email):
        response = self.client.post(self.url, {"email": "Person@Example.com", "password": "Str0ng!Pass"}, format="json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "TOKEN_CREATED")
        self.assertIn("access", body["data"])
        self.assertIn("refresh", body["data"])
        self.assertEqual(body["data"]["user"]["email"], "person@example.com")
        mock_send_email.assert_not_called()
        mock_send_email.delay.assert_not_called()

    def test_access_token_authenticates_user_endpoint(self):
        response = self.client.post(self.url, {"email": "person@example.com", "password": "Str0ng!Pass"}, format="json")
        access = response.json()["data"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me = self.client.get("/api/user/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["email"], "person@example.com")

    def test_wrong_password_is_rejected(self):
        response = self.client.post(self.url, {"email": "person@example.com", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "LOGIN_FAILED")

    def test_missing_fields_are_rejected(self):
        response = self.client.post(self.url, {"email": "person@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "INVALID_INPUT")

    def test_blocked_account_is_rejected(self):
        self.user.waiting_period = timezone.now() + timedelta(minutes=10)
        self.user.save()
        response = self.client.post(self.url, {"email": "person@example.com", "password": "Str0ng!Pass"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_repeated_failures_lock_out(self):
        for _ in range(7):
            self.client.post(self.url, {"email": "person@example.com", "password": "wrong"}, format="json")
        response = self.client.post(self.url, {"email": "person@example.com", "password": "Str0ng!Pass"}, format="json")
        self.assertEqual(response.status_code, 403)
