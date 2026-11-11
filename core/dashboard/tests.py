from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.dpmes import client as dpmes_client
from users.models import Ministry

PAGES = [
    ("dashboard_home", {}), ("dashboard_about", {}), ("dashboard_admas_ai", {}), ("data_categories", {}),
    ("data_topic_detail", {"topic_id": 1}), ("data_indicator_detail", {"indicator_id": 1}),
    ("policy_area_list", {}), ("policy_area_detail", {"policy_area_id": 47}),
    ("public_body_list", {}), ("public_body_detail", {"ministry_id": 312}), ("goal_detail", {"goal_id": 983}),
    ("high_frequency_dashboard", {}), ("sector_project_list", {}), ("sector_project_detail", {"project_id": 1}),
    ("initiative_list", {}), ("initiative_detail", {"initiative_id": 1}),
    ("sdg_list", {}), ("sdg_detail", {"goal_id": 3}), ("sdg_data", {"goal_id": 3}),
    ("edit_profile", {}), ("change_password", {}),
]
PASSWORD = "Str0ng!pass"


class DashboardTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dash", email="dash@example.test", password=PASSWORD)
        self.client.defaults["HTTP_HOST"] = "localhost"


class AccessTests(DashboardTestCase):
    def test_every_page_sends_anonymous_visitors_to_the_login_page(self):
        for name, kwargs in PAGES:
            url = reverse(name, kwargs=kwargs)
            response = self.client.get(url)
            self.assertRedirects(response, f"/dashboard/login/?next={url}", fetch_redirect_response=False, msg_prefix=name)

    def test_every_page_renders_for_a_signed_in_user(self):
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        for name, kwargs in PAGES:
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, 200, name)
            self.assertIn("text/html", response["Content-Type"], name)

    def test_privacy_policy_is_public(self):
        for path in ("/privacy-policy/", "/privacy_policy/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertContains(response, "Ministry of National Strategy")


class LoginTests(DashboardTestCase):
    def login(self, password=PASSWORD, next_url=None, email="Dash@Example.test"):
        data = {"email": email, "password": password}
        if next_url:
            data["next"] = next_url
        return self.client.post("/dashboard/login/", data)

    def test_email_and_password_sign_in_and_follow_next(self):
        response = self.login(next_url="/dashboard/statistics/policy-areas/")
        self.assertRedirects(response, "/dashboard/statistics/policy-areas/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_wrong_password_shows_an_error(self):
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)

    def test_next_cannot_send_the_user_to_another_site(self):
        response = self.login(next_url="https://evil.example/steal")
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_logout_ends_the_session(self):
        self.login()
        self.assertRedirects(self.client.get("/dashboard/logout/"), "/dashboard/login/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)


class OrganizationOverviewTests(DashboardTestCase):
    URL = "/dashboard/api/organization-overview/"

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def set_ministry(self, **fields):
        ministry = Ministry.objects.create(name="Ministry of Health", abbreviation="MoH", **fields)
        self.user.ministry = ministry
        self.user.save(update_fields=["ministry"])
        return ministry

    def test_user_without_an_organization(self):
        self.user.ministry = None
        self.user.save(update_fields=["ministry"])
        response = self.client.get(self.URL)
        self.assertEqual((response.status_code, response.json()["message"]), (400, "NO_MINISTRY"))

    def test_organization_not_linked_to_dpmes(self):
        self.set_ministry()
        self.assertEqual(self.client.get(self.URL).json()["message"], "MINISTRY_NOT_LINKED")

    def test_overview_of_the_users_organization(self):
        self.set_ministry(dpmes2_id=312)
        scorecard = {"id": 312, "name": "Ministry of Health", "score": {"avg_score": 80.12},
                     "policy_areas": [{"id": 47}], "performance_analysis": {"on_track": 72}}
        with patch.object(dpmes_client, "is_configured", return_value=True), \
                patch.object(dpmes_client, "organization_scorecard", return_value=scorecard) as fetch, \
                patch.object(dpmes_client, "score_ranges", return_value=[{"name_en": "On Track"}]):
            response = self.client.get(self.URL + "?year=2017&quarter=2")
        fetch.assert_called_once_with(312, {"year": "2017", "quarter": "2"})
        data = response.json()["data"]
        self.assertEqual((data["ministry"]["abbreviation"], data["ministry"]["dpmes2_id"]), ("MoH", 312))
        self.assertEqual(data["detail"]["policy_areas"], [{"id": 47}])
        self.assertEqual(data["performance"]["score"], {"avg_score": 80.12})

    def test_dpmes_failure_is_reported(self):
        self.set_ministry(dpmes2_id=312)
        with patch.object(dpmes_client, "is_configured", return_value=True), \
                patch.object(dpmes_client, "organization_scorecard", side_effect=dpmes_client.DPMES2Error("down")):
            response = self.client.get(self.URL + "?year=2017")
        self.assertEqual((response.status_code, response.json()["message"]), (502, "down"))
