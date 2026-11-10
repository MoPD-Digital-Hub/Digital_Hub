import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from rest_framework.test import APIClient

from project.responses import LEGACY_SUCCESS, complete, failure, success

STANDARD_KEYS = {"result", "message", "request_id", "data"}


class HelperTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.request_id = "req-1"

    def test_success(self):
        body = success(self.request, [1], message="LOADED").data
        self.assertEqual(body, {"result": "SUCCESS", "message": "LOADED", "request_id": "req-1", "data": [1]})

    def test_failure_keeps_the_message_and_adds_a_code(self):
        body = failure(self.request, "Too many failed attempts.", 403).data
        self.assertEqual(body["message"], "Too many failed attempts.")
        self.assertEqual(body["error"], {"code": "FORBIDDEN", "message": "Too many failed attempts.", "details": {}})

    def test_message_that_is_a_code_becomes_the_code(self):
        self.assertEqual(failure(self.request, "LOGIN_FAILED", 401).data["error"]["code"], "LOGIN_FAILED")

    def test_legacy_field_errors_are_kept_and_mirrored(self):
        body = failure(self.request, "INVALID_INPUT", 400, errors={"email": ["Required."]}).data
        self.assertEqual(body["errors"], {"email": ["Required."]})
        self.assertEqual(body["error"]["details"], {"email": ["Required."]})


class CompleteTests(SimpleTestCase):
    """complete() only adds fields; every existing field keeps its exact value."""

    def setUp(self):
        self.request = RequestFactory().get("/api/x")
        self.request.request_id = "req-2"

    def assertOnlyAdded(self, original, completed):
        for key, value in original.items():
            self.assertEqual(completed[key], value, key)

    def test_bare_object_keeps_its_fields_and_gains_data(self):
        original = {"years": [2017]}
        body = complete(original, 200, self.request)
        self.assertOnlyAdded(original, body)
        self.assertEqual(body["data"], {"years": [2017]})
        self.assertEqual((body["result"], body["request_id"]), ("SUCCESS", "req-2"))

    def test_existing_values_are_never_changed(self):
        original = {"result": LEGACY_SUCCESS, "message": LEGACY_SUCCESS, "data": [1]}
        body = complete(original, 200, self.request)
        self.assertOnlyAdded(original, body)
        self.assertEqual(set(body) - set(original), {"request_id"})

    def test_upstream_failure_gains_an_error_object(self):
        original = {"result": "FAILED", "message": "Topic not found", "data": None}
        body = complete(original, 404, self.request)
        self.assertOnlyAdded(original, body)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_framework_error_keeps_detail_and_gains_the_shape(self):
        original = {"detail": "Authentication credentials were not provided.", "code": "not_authenticated"}
        body = complete(original, 403, self.request)
        self.assertOnlyAdded(original, body)
        self.assertEqual(body["result"], "FAILURE")
        self.assertEqual(body["message"], "Authentication credentials were not provided.")
        self.assertEqual(body["error"]["code"], "not_authenticated")

    def test_a_string_error_is_left_as_is(self):
        original = {"error": "Both 'category_id' and 'name' are required."}
        body = complete(original, 400, self.request)
        self.assertOnlyAdded(original, body)
        self.assertEqual(body["message"], original["error"])

    def test_lists_are_left_alone(self):
        self.assertEqual(complete([1, 2], 200, self.request), [1, 2])


class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="v", email="v@example.test", password="Str0ng!pass")
        self.client = APIClient()

    def test_framework_errors_keep_detail_and_gain_the_shape(self):
        response = self.client.get("/api/user/", HTTP_HOST="localhost")
        body = json.loads(response.content)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["detail"], "Authentication credentials were not provided.")
        self.assertEqual(body["code"], "not_authenticated")
        self.assertTrue(STANDARD_KEYS <= set(body))
        self.assertEqual(body["error"]["code"], "not_authenticated")
        if response.has_header("Content-Length"):
            self.assertEqual(int(response["Content-Length"]), len(response.content))

    def test_existing_result_values_are_unchanged(self):
        self.client.force_authenticate(self.user)
        body = self.client.get("/api/mobile/setting/", HTTP_HOST="localhost").json()
        self.assertEqual(body["result"], LEGACY_SUCCESS)  # what installed app versions receive today
        self.assertTrue(STANDARD_KEYS <= set(body))

    def test_invalid_refresh_token_is_401_not_500(self):
        response = self.client.post("/api/auth/token/refresh/", {"refresh": "not-a-token"}, format="json",
                                    HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "token_not_valid")
