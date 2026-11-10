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

    @patch("users.views.send_email")
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
