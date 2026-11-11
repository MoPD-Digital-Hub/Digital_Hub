from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from integrations.dpmes import client, compat

RANGES = [
    {"name_en": "Achieved", "start": "95", "end": "100", "color": "#0a0"},
    {"name_en": "On Track", "start": "80", "end": "94.99", "color": "#5d9444"},
    {"name_en": "In Progress", "start": "60", "end": "79.99", "color": "#fc0"},
    {"name_en": "Weak Performance", "start": "0", "end": "59.99", "color": "#f00"},
    {"name_en": "No Data", "start": "-1", "end": "-1", "color": "#ccc", "is_default": True},
]
ORG_ROW = {"id": 312, "name": "Ministry of Health", "name_eth": "ጤና ሚኒስቴር", "code": "MoH", "icon": "/i.png",
           "score": {"avg_score": 80.12, "color": "#5d9444", "total_weight": 100}, "order": 3, "parent": 1}


class PeriodTests(SimpleTestCase):
    def test_legacy_quarter_labels_become_numbers(self):
        self.assertEqual(compat.build_period({"year": "2017", "quarter": "9month"}), {"year": "2017", "quarter": 3})

    def test_numeric_quarter_month_and_plan_pass_through(self):
        period = compat.build_period({"year": "2017", "quarter": "2", "month": "5", "plan": "7"})
        self.assertEqual(period, {"year": "2017", "quarter": 2, "month": "5", "plan": "7"})

    def test_unknown_quarter_is_dropped_and_year_defaults_to_the_current_one(self):
        with patch.object(client, "current_ethiopian_year", return_value=2019):
            self.assertEqual(compat.build_period({"quarter": "soon"}), {"year": 2019})


class MappingTests(SimpleTestCase):
    """DPMES field names -> the names the website's scorecard scripts read."""

    def test_ministry(self):
        row = compat.ministry(ORG_ROW, rank=9)
        self.assertEqual(row["responsible_ministry_eng"], "Ministry of Health")
        self.assertEqual(row["responsible_ministry_amh"], "ጤና ሚኒስቴር")
        self.assertEqual(row["ministry_score_card"],
                         {"avg_score": 80.12, "scorecard_color": "#5d9444", "total_weight": 100})
        self.assertEqual((row["image"], row["ministry_rank"], row["ministry_is_visable"]), ("/i.png", 3, True))

    def test_ministry_without_a_score_or_amharic_name(self):
        row = compat.ministry({"id": 1, "trans_name": "Agency"}, rank=4)
        self.assertEqual((row["responsible_ministry_eng"], row["responsible_ministry_amh"]), ("Agency", "Agency"))
        self.assertEqual(row["ministry_score_card"], {"avg_score": None, "scorecard_color": None, "total_weight": None})
        self.assertEqual(row["ministry_rank"], 4)

    def test_policy_area(self):
        row = compat.policy_area({"id": 47, "name": "Health", "code": "PA-1", "score": {"avg_score": 69.39}}, rank=2)
        self.assertEqual((row["policyAreaEng"], row["policyAreaCode"], row["rank"]), ("Health", "PA-1", 2))
        self.assertEqual(row["policy_area_score_card"]["avg_score"], 69.39)

    def test_map_rows_ranks_from_one_and_skips_junk(self):
        rows = compat.map_rows([{"id": 1, "name": "A"}, "junk", {"id": 2, "name": "B"}], compat.policy_area)
        self.assertEqual([(r["id"], r["rank"]) for r in rows], [(1, 1), (2, 3)])
        self.assertEqual(compat.map_rows(None, compat.policy_area), [])

    def test_organization_policy_areas_link_goals_to_the_organization(self):
        areas = compat.organization_policy_areas({"id": 312, "policy_areas": [
            {"id": 47, "name": "Health", "score": {"avg_score": 80}, "goals": [{"id": 983, "name": "Maternal health"}]}]})
        self.assertEqual(areas[0]["policy_area_goal"][0]["responsible_ministries"], 312)
        self.assertEqual(areas[0]["ministry_policy_area_score_card"]["avg_score"], 80)

    def test_find_goal_score(self):
        card = {"policy_areas": [{"goals": [{"id": 983, "score": {"avg_score": 90.85, "color": "#0a0"}}]}]}
        self.assertEqual(compat.find_goal_score(card, "983")["avg_score"], 90.85)
        self.assertIsNone(compat.find_goal_score(card, 1))
        self.assertIsNone(compat.find_goal_score(None, 1))


class IndicatorTests(SimpleTestCase):
    KPI = {"id": 6374, "name": "Vitamin A coverage", "code": "K-1", "weight": 5, "records": [
        {"id": 1, "record_type": "quarterly", "ethio_date": "2018-02", "target": 100, "performance": 92, "score": 92,
         "score_color": "#5d9444"},
        {"id": 2, "record_type": "yearly", "ethio_date": "2017", "target": 100, "performance": 80, "score": 80},
    ]}

    def test_records_are_split_into_annual_and_quarterly(self):
        item = compat.indicator(self.KPI)
        self.assertEqual(item["kpi_name_eng"], "Vitamin A coverage")
        self.assertEqual(item["quarter_indicators"], [{
            "id": 1, "year": 2018, "score": 92, "scorecard": "#5d9444", "indicator": 6374,
            "indicator_name": "Vitamin A coverage", "quarter": "6month", "quarter_target": 100, "quarter_performance": 92}])
        self.assertEqual(item["annual_indicators"][0]["annual_performance"], 80)
        self.assertEqual(item["annual_indicators"][0]["year"], 2017)

    def test_range_for_score(self):
        self.assertEqual(compat.range_for_score(92, RANGES)["name_en"], "On Track")
        self.assertEqual(compat.range_for_score(None, RANGES)["name_en"], "No Data")
        self.assertEqual(compat.range_for_score(250, RANGES)["name_en"], "No Data")

    def test_goal_detail_buckets_kpis_and_uses_the_given_goal_score(self):
        data = {"id": 983, "name": "Maternal health", "kras": [{
            "id": 5, "name": "Nutrition", "score": {"total_score": 45, "total_weight": 50, "avg_score": 90},
            "kpis": [self.KPI, {"id": 7, "name": "No records yet", "records": []}]}]}
        detail = compat.goal_detail(data, RANGES, goal_score={"avg_score": 90.85})
        self.assertEqual(detail["goal_score_card"], {"avg_score": 90.85})
        self.assertEqual(detail["kra_goal"][0]["activity_name_eng"], "Nutrition")
        self.assertEqual(len(detail["kra_goal"][0]["indicators"]), 2)
        self.assertEqual((detail["good_performance"]["count"], detail["no_performance"]["count"]), (1, 1))
        self.assertEqual(detail["good_performance"]["percentage"], 50.0)
        self.assertEqual(detail["no_performance"]["data"][0]["indicator_name"], "No records yet")

    def test_goal_detail_derives_the_score_when_none_is_given(self):
        data = {"id": 1, "name": "G", "kras": [{"id": 5, "name": "K", "score": {"total_score": 45, "total_weight": 50}}]}
        self.assertEqual(compat.goal_detail(data, RANGES)["goal_score_card"],
                         {"avg_score": 90.0, "scorecard_color": "#5d9444", "total_weight": 50.0})

    def test_organization_performance_buckets(self):
        buckets = compat.organization_performance([
            {"name_en": "Achieved", "color": "#0a0", "kpis": [{"id": 1, "name": "A", "records": [{"score": 99}]}]},
            {"name_en": "Requires Intervention", "color": "#900", "kpis": [{"id": 2, "name": "B", "records": []}]},
            {"name_en": "Something new", "kpis": [{"id": 3, "name": "C"}]},
        ])
        self.assertEqual(buckets["on_track"], [{"indicator": 1, "indicator_name": "A", "score": 99, "scorecard": "#0a0"}])
        self.assertEqual(buckets["weak_performance"][0]["scorecard"], "#900")
        self.assertEqual([k["indicator"] for k in buckets["no_data"]], [3])  # unknown ranges are not dropped
        self.assertEqual(buckets["in_progress"], [])


@override_settings(DPMES2_API_BASE="https://dpmes.test", DPMES2_API_KEY="key-1")
class ClientTests(SimpleTestCase):
    def response(self, status=200, payload=None, json_error=False):
        response = Mock(status_code=status)
        response.json = Mock(side_effect=ValueError("no json")) if json_error else Mock(return_value=payload)
        return response

    def test_sends_the_key_and_unwraps_data(self):
        with patch("integrations.dpmes.client.requests.get", return_value=self.response(payload={"data": [1]})) as get:
            self.assertEqual(client.get("/x/", {"year": 2017}), [1])
        self.assertEqual(get.call_args.args[0], "https://dpmes.test/x/")
        self.assertEqual(get.call_args.kwargs["headers"], {"X-API-Key": "key-1"})

    def test_failures_become_dpmes_errors(self):
        cases = [
            ({"side_effect": requests.exceptions.ConnectionError("down")}, "Failed to reach DPMES2"),
            ({"return_value": self.response(status=403)}, "rejected the API key"),
            ({"return_value": self.response(status=500)}, "HTTP 500"),
            ({"return_value": self.response(json_error=True)}, "non-JSON"),
        ]
        for kwargs, message in cases:
            with patch("integrations.dpmes.client.requests.get", **kwargs), self.assertRaisesMessage(
                    client.DPMES2Error, message):
                client.get("/x/")


class EndpointTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="d", email="d@example.test", password="Str0ng!pass")
        self.client = APIClient()
        self.client.force_authenticate(user)

    def get(self, path):
        return self.client.get(path, HTTP_HOST="localhost")

    def test_requires_sign_in(self):
        self.assertEqual(APIClient().get("/api/mobile/ministries/", HTTP_HOST="localhost").status_code, 403)

    def test_ministries(self):
        with patch.object(client, "child_organizations", return_value=[ORG_ROW]) as fetch:
            body = self.get("/api/mobile/ministries/?year=2017&quarter=6month").json()
        fetch.assert_called_once_with({"year": "2017", "quarter": 2})
        self.assertEqual(body["result"], "SUCCESS")
        self.assertEqual(body["data"][0]["responsible_ministry_eng"], "Ministry of Health")

    def test_dpmes_failure_is_a_502_with_the_reason(self):
        with patch.object(client, "policy_area_scores", side_effect=client.DPMES2Error("DPMES2 returned HTTP 500.")):
            response = self.get("/api/mobile/policy-areas/?year=2017")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "DPMES2 returned HTTP 500.")
        self.assertEqual(response.json()["error"]["code"], "UPSTREAM_ERROR")

    def test_default_time_is_the_last_completed_year(self):
        with patch.object(client, "current_ethiopian_year", return_value=2019):
            data = self.get("/api/mobile/default-time/").json()["data"]
        self.assertEqual(data, {"year": 2018, "quarter": "12month", "is_quarter": False})

    def test_performance_buckets_stay_at_the_top_level_and_under_data(self):
        rows = [{"name_en": "On Track", "kpis": [{"id": 1, "name": "A", "records": [{"score": 90}]}]}]
        with patch.object(client, "kpis_by_score_range", return_value=rows):
            body = self.get("/api/mobile/ministry-performance/312/?year=2017").json()
        self.assertEqual(len(body["on_track"]), 1)          # what the page has always read
        self.assertEqual(body["data"]["on_track"], body["on_track"])

    def test_goal_detail_falls_back_to_the_keys_organization(self):
        with patch.object(client, "key_organization_id", return_value=1) as key_org, \
                patch.object(client, "goal_kras", return_value={"id": 983, "name": "G", "kras": []}) as kras, \
                patch.object(client, "organization_scorecard", return_value={}), \
                patch.object(client, "score_ranges", return_value=RANGES):
            body = self.get("/api/mobile/goal-detail/983/?year=2017").json()
        key_org.assert_called_once()
        self.assertEqual(kras.call_args.args[:2], ("983", 1))
        self.assertEqual(body["data"]["goal_name_eng"], "G")
