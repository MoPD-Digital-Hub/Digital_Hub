from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from mobile.models import FAQ, AppVersion
from mobile.validators import StrongPasswordValidator


class CheckUpdateTests(TestCase):
    """GET /api/mobile/check-update/?version=…  (public: the app calls it before sign-in)."""

    def check(self, version=None):
        path = "/api/mobile/check-update/" + (f"?version={version}" if version is not None else "")
        return APIClient().get(path, HTTP_HOST="localhost")

    def test_version_is_required(self):
        response = self.check()
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (400, "VERSION_REQUIRED"))
        self.assertEqual(response.json()["detail"], "version query param is required")  # field old app versions read

    def test_no_version_configured(self):
        self.assertEqual(self.check("1.0.0").json()["error"]["code"], "NO_VERSION_INFO")

    def test_update_decisions(self):
        AppVersion.objects.create(latest_version="2.1.0", min_supported_version="2.0.0", message="Please update")
        cases = {
            "1.9.9": (True, False, "Please update"),    # below the minimum: forced
            "2.0.0": (False, True, ""),                 # supported but behind: optional
            "2.0.10": (False, True, ""),                # compared as versions, not text
            "2.1.0": (False, False, ""),
            "3.0.0": (False, False, ""),                # ahead of the store (test builds)
        }
        for version, (force, optional, message) in cases.items():
            data = self.check(version).json()["data"]
            self.assertEqual((data["force_update"], data["optional_update"], data["message"]), (force, optional, message),
                             version)
            self.assertEqual(data["latest_version"], "2.1.0")

    def test_the_latest_row_wins(self):
        AppVersion.objects.create(latest_version="1.0.0", min_supported_version="1.0.0")
        AppVersion.objects.create(latest_version="2.0.0", min_supported_version="1.5.0")
        self.assertEqual(self.check("1.0.0").json()["data"]["force_update"], True)

    def test_a_malformed_version_is_a_400_not_a_crash(self):
        AppVersion.objects.create(latest_version="2.1.0", min_supported_version="2.0.0")
        response = self.check("not-a-version")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (400, "VERSION_INVALID"))


class ContentTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="m", email="m@example.test", password="Str0ng!pass")
        self.api = APIClient()
        self.api.force_authenticate(user)

    def test_content_endpoints_need_sign_in(self):
        for path in ("setting/", "faq/", "contact-us/", "dashboard/apps/"):
            self.assertEqual(APIClient().get("/api/mobile/" + path, HTTP_HOST="localhost").status_code, 403, path)

    def test_content_endpoints_answer_in_the_standard_shape(self):
        for path in ("setting/", "contact-us/", "dashboard/apps/"):
            body = self.api.get("/api/mobile/" + path, HTTP_HOST="localhost").json()
            self.assertEqual(body["data"], [], path)
            self.assertTrue({"result", "message", "request_id", "data"} <= set(body), path)

    def test_faq_is_grouped_by_type(self):
        field_names = {f.name for f in FAQ._meta.get_fields()}
        self.assertIn("type", field_names)
        body = self.api.get("/api/mobile/faq/", HTTP_HOST="localhost").json()
        self.assertEqual((body["result"], body["data"]), ("SUCCESS", {}))


class PasswordValidatorTests(SimpleTestCase):
    def test_strong_password_passes(self):
        StrongPasswordValidator().validate("Str0ng!pass")

    def test_each_missing_ingredient_is_rejected(self):
        for weak in ("Sh0rt!", "nouppercase1!", "NOLOWERCASE1!", "NoNumber!!", "NoSpecial11"):
            with self.assertRaises(ValidationError, msg=weak):
                StrongPasswordValidator().validate(weak)
