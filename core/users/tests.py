from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import CustomUser


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

    @patch("users.api.views.send_email")
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


class OtpSignInRemovedTests(TestCase):
    """Sign-in is email + password only; the emailed sign-in code is gone."""

    def test_the_otp_sign_in_endpoints_no_longer_exist(self):
        client = APIClient()
        for path in ("/api/user/auth/login/", "/api/user/auth/verify-otp/"):
            response = client.post(path, {"email": "person@example.com", "password": "x", "otp": "123456"}, format="json")
            self.assertEqual(response.status_code, 404, path)


class PasswordResetTests(TestCase):
    """POST /api/user/reset-password/ emails a code; PUT sets a new password with it."""

    url = "/api/user/reset-password/"
    NEW_PASSWORD = "N3w!Password"

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(email="person@example.com", username="person", password="Str0ng!Pass")

    def request_code(self):
        with patch("users.api.views.send_email") as send_email:
            response = self.client.post(self.url, {"email": "Person@Example.com"}, format="json")
        self.user.refresh_from_db()
        return response, send_email

    def confirm(self, code, password=None):
        payload = {"email": "person@example.com", "token": code, "password": password or self.NEW_PASSWORD}
        return self.client.put(self.url, payload, format="json")

    def test_a_six_digit_code_is_emailed_and_expires_in_twenty_minutes(self):
        response, send_email = self.request_code()
        self.assertEqual((response.status_code, response.json()["message"]), (200, "EMAIL_SENT"))
        self.assertIsNone(response.json()["data"])            # the code is never in the response
        self.assertRegex(self.user.token, r"^[0-9]{6}$")
        send_email.assert_called_once_with("person@example.com", self.user.token)
        lifetime = self.user.tokenExpiration - timezone.now()
        self.assertTrue(timedelta(minutes=19) < lifetime <= timedelta(minutes=20))

    def test_the_code_sets_a_new_password_once(self):
        self.request_code()
        code = self.user.token
        response = self.confirm(code)
        self.assertEqual((response.status_code, response.json()["message"]), (200, "PASSWORD_CHANGED"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.NEW_PASSWORD))
        self.assertEqual(self.confirm(code, "An0ther!Pass").json()["message"], "INVALID_TOKEN")   # used up
        signed_in = self.client.post("/api/user/auth/password-login/",
                                     {"email": "person@example.com", "password": self.NEW_PASSWORD}, format="json")
        self.assertEqual(signed_in.status_code, 200)

    def test_wrong_expired_and_missing_codes_are_rejected(self):
        self.assertEqual(self.confirm("123456").json()["message"], "INVALID_TOKEN")      # none requested
        self.request_code()
        wrong = "000000" if self.user.token != "000000" else "111111"
        self.assertEqual(self.confirm(wrong).json()["message"], "INVALID_TOKEN")
        CustomUser.objects.filter(pk=self.user.pk).update(tokenExpiration=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirm(self.user.token).json()["message"], "TOKEN_EXPIRED")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Str0ng!Pass"))                          # unchanged throughout

    def test_five_wrong_codes_cancel_the_code(self):
        self.request_code()
        code = self.user.token
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.confirm(wrong).json()["message"], "INVALID_TOKEN")
        # The right code no longer works: guessing cannot continue against the same code.
        self.assertEqual(self.confirm(code).json()["message"], "INVALID_TOKEN")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Str0ng!Pass"))
        # A newly requested code works, with a fresh count of tries.
        self.request_code()
        self.assertEqual(self.confirm(self.user.token).json()["message"], "PASSWORD_CHANGED")

    def test_weak_passwords_and_unknown_emails_are_rejected(self):
        self.request_code()
        self.assertEqual(self.confirm(self.user.token, "weak").status_code, 400)
        response = self.client.post(self.url, {"email": "nobody@example.com"}, format="json")
        self.assertEqual((response.status_code, response.json()["message"]), (400, "USER_NOT_FOUND"))


class AdoptMigrationsTests(TransactionTestCase):
    """manage.py adopt_migrations: rewrite stale migration history, but only when the schema matches."""

    def setUp(self):
        from django.db import connection
        from django.db.migrations.recorder import MigrationRecorder

        self.recorder = MigrationRecorder(connection)
        self.saved = list(self.recorder.migration_qs.values_list("app", "name"))

    def tearDown(self):
        self.recorder.migration_qs.all().delete()
        for app, name in self.saved:
            self.recorder.record_applied(app, name)

    def _stale_history(self):
        self.recorder.migration_qs.filter(app="AI").delete()
        for name in ("0001_initial", "0002_initial", "0003_generated_on_the_server"):
            self.recorder.record_applied("AI", name)

    def test_matching_history_needs_nothing(self):
        from django.core.management import call_command

        call_command("adopt_migrations", "--check", stdout=StringIO())

    def test_stale_history_is_adopted(self):
        from django.core.management import CommandError, call_command

        self._stale_history()
        with self.assertRaises(CommandError):
            call_command("adopt_migrations", "--check", stdout=StringIO())
        call_command("adopt_migrations", "--apply", stdout=StringIO())
        names = set(self.recorder.migration_qs.filter(app="AI").values_list("name", flat=True))
        self.assertEqual(names, {"0001_initial", "0002_initial"})

    def test_migrations_after_the_baseline_are_left_for_migrate(self):
        from django.core.management import call_command

        self._stale_history()
        out = StringIO()
        call_command("adopt_migrations", "--apply", stdout=out)
        recorded = set(self.recorder.migration_qs.filter(app="Notification").values_list("name", flat=True))
        self.assertEqual(recorded, {"0001_initial", "0002_initial"})          # 0003 must really run
        self.assertIn("Notification.0003_notification_sent_at", out.getvalue())
        # An adopted database with newer migrations pending no longer needs adopting.
        call_command("adopt_migrations", "--check", stdout=StringIO())

    def test_refuses_when_a_column_is_missing(self):
        from django.core.management import CommandError, call_command
        from django.db import connection

        self._stale_history()
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE "AI_loadedfile" RENAME COLUMN "number" TO "number_renamed"')
        try:
            with self.assertRaisesMessage(CommandError, 'missing column AI_loadedfile.number'):
                call_command("adopt_migrations", "--apply", stdout=StringIO())
            self.assertIn("0003_generated_on_the_server",
                          set(self.recorder.migration_qs.filter(app="AI").values_list("name", flat=True)))
        finally:
            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE "AI_loadedfile" RENAME COLUMN "number_renamed" TO "number"')
