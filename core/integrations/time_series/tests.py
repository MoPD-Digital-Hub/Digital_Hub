from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from integrations.time_series import client

BASE = "https://ts.test/api/mobile"


def upstream(payload=None, status=200, content=b"", headers=None):
    response = Mock(status_code=status, content=content, headers=headers or {})
    response.json = Mock(return_value=payload)
    return response


class ClientTests(SimpleTestCase):
    def test_base_url_comes_from_the_environment(self):
        with patch.dict("os.environ", {"TIME_SERIES_API_BASE": BASE + "/"}):
            self.assertEqual(client.base_url(), BASE)
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(client.base_url(), client.DEFAULT_BASE_URL)

    def test_fetch_topics_reads_each_topics_detail(self):
        session = Mock()
        session.get.side_effect = [
            upstream({"data": [{"id": 1}, {"id": 2}]}),
            upstream({"data": {"id": 1, "title_ENG": "Macro"}}),
            upstream({"data": {"id": 2, "title_ENG": "Trade"}}),
        ]
        with patch.object(client, "base_url", return_value=BASE):
            topics = client.fetch_topics(session)
        self.assertEqual([t["title_ENG"] for t in topics], ["Macro", "Trade"])
        self.assertEqual([call.args[0] for call in session.get.call_args_list],
                         [f"{BASE}/topic-list/", f"{BASE}/topic-detail/1/", f"{BASE}/topic-detail/2/"])


@patch.object(client, "base_url", return_value=BASE)
class EndpointTests(TestCase):
    """The /api/mobile/ endpoints pass the service's response through."""

    def setUp(self):
        user = get_user_model().objects.create_user(username="t", email="t@example.test", password="Str0ng!pass")
        self.client = APIClient()
        self.client.force_authenticate(user)

    def get(self, path):
        return self.client.get(path, HTTP_HOST="localhost")

    def test_requires_sign_in(self, _base):
        self.assertEqual(APIClient().get("/api/mobile/topic-list/", HTTP_HOST="localhost").status_code, 403)

    def test_body_status_and_query_pass_through(self, _base):
        payload = {"result": "SUCCUSS", "message": "SUCCUSS", "data": [{"id": 28}]}
        with patch("integrations.time_series.views.requests.get", return_value=upstream(payload)) as get:
            response = self.get("/api/mobile/topic-list/?lang=am")
        self.assertEqual(get.call_args.args[0], f"{BASE}/topic-list/")
        self.assertEqual(get.call_args.kwargs["params"], {"lang": "am"})
        body = response.json()
        self.assertEqual({k: body[k] for k in payload}, payload)   # exactly what the service sent
        self.assertIn("request_id", body)

    def test_upstream_error_status_is_kept(self, _base):
        payload = {"result": "FAILED", "message": "Topic not found", "data": None}
        with patch("integrations.time_series.views.requests.get", return_value=upstream(payload, status=404)):
            response = self.get("/api/mobile/categories/1/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "Topic not found")
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_unreachable_service_is_a_502(self, _base):
        error = requests.exceptions.ConnectionError("refused")
        with patch("integrations.time_series.views.requests.get", side_effect=error):
            response = self.get("/api/mobile/trending/")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Failed to reach Time-Series service", response.json()["detail"])
        self.assertEqual(response.json()["error"]["code"], "UPSTREAM_ERROR")

    def test_exports_pass_the_file_through_untouched(self, _base):
        headers = {"Content-Type": "application/vnd.ms-excel", "Content-Disposition": 'attachment; filename="t.xlsx"'}
        file = upstream(content=b"PK\x03\x04 spreadsheet bytes", headers=headers)
        with patch("integrations.time_series.views.requests.get", return_value=file) as get:
            response = self.get("/api/mobile/export-topic-data/28/?data_type=annual&file_type=xlsx")
        self.assertEqual(get.call_args.args[0], f"{BASE}/export-topic-data/28/")
        self.assertEqual(response.content, b"PK\x03\x04 spreadsheet bytes")
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="t.xlsx"')
