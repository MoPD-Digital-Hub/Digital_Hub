from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from integrations.dpmes import client as dpmes_client
from integrations.time_series import client as time_series_client
from preferences import dashboard, sources
from preferences.models import SECTIONS, Follow, UserPreference
from users.models import Ministry

RANGES = [
    {"name_en": "No Data", "start": "-10", "end": "-1", "color": "#444", "is_default": True},
    {"name_en": "Requires Intervention", "start": "0", "end": "49.99", "color": "#f00"},
    {"name_en": "Weak Performance", "start": "50", "end": "64.99", "color": "#f70"},
    {"name_en": "In Progress", "start": "65", "end": "79.99", "color": "#fb0"},
    {"name_en": "On Track", "start": "80", "end": "94.99", "color": "#6c2"},
    {"name_en": "Achieved", "start": "95", "end": "100", "color": "#062"},
]


def org(identifier, name, code, score):
    return {"id": identifier, "name": name, "name_eth": f"{name} (am)", "code": code, "icon": "/i.png",
            "score": {"avg_score": score, "color": "#abc"}}


def kpi(identifier, name, category, score, performance=10, target=10, characteristics="Increasing"):
    records = [] if score is None else [
        {"score": score, "performance": performance, "target": target, "score_color": "#abc"},
    ]
    return {"id": identifier, "name": name, "name_eth": "", "code": f"K-{identifier}", "for_category": category,
            "measurement_units": "Percentage", "kpi_characteristics": characteristics, "records": records}


class FakeDPMES:
    """Stands in for the DPMES client: scores by period, as the real service returns them."""

    year = 2019
    organizations = {
        "2019-1": [org(312, "Ministry of Health", "MoH", 70.0), org(313, "Ministry of Peace", "MoP", 90.0),
                   org(314, "Ministry of Water", "MoWE", 0.0)],
        "2018-4": [org(312, "Ministry of Health", "MoH", 80.0), org(313, "Ministry of Peace", "MoP", 85.0),
                   org(314, "Ministry of Water", "MoWE", 60.0)],
        "2018": [org(312, "Ministry of Health", "MoH", 66.0), org(313, "Ministry of Peace", "MoP", 91.0),
                 org(314, "Ministry of Water", "MoWE", 0.0)],
        "2017": [org(312, "Ministry of Health", "MoH", 80.0), org(313, "Ministry of Peace", "MoP", 87.0)],
    }
    policy_areas = {
        "2019-1": [org(47, "Macroeconomy", "PA-001", 40.0), org(61, "Health", "PA-015", 88.0)],
        "2018-4": [org(47, "Macroeconomy", "PA-001", 55.0), org(61, "Health", "PA-015", 80.0)],
        "2018": [org(47, "Macroeconomy", "PA-001", 50.0), org(61, "Health", "PA-015", 82.0)],
    }
    kpis = {
        ("312", "2019-1"): [kpi(1, "Ambulance response", "Emergency care", 100.0),
                            kpi(2, "Maternal deaths", "Maternal health", 40.0),
                            kpi(3, "Clinic visits", "Maternal health", 70.0),
                            kpi(4, "Not reported", "Emergency care", None)],
        ("312", "2018-4"): [kpi(1, "Ambulance response", "Emergency care", 80.0),
                            kpi(2, "Maternal deaths", "Maternal health", 90.0),
                            kpi(3, "Clinic visits", "Maternal health", 60.0),
                            kpi(4, "Not reported", "Emergency care", 50.0)],
        ("312", "2018"): [kpi(1, "Ambulance response", "Emergency care", 100.0)],
    }
    down = False

    def key(self, period):
        return sources.period_key({"year": int(period["year"]), "quarter": period.get("quarter")})

    def check(self):
        if self.down:
            raise dpmes_client.DPMES2Error("Failed to reach DPMES2: timed out")

    def child_organizations(self, period=None):
        self.check()
        return self.organizations.get(self.key(period), [])

    def policy_area_scores(self, period=None):
        self.check()
        return self.policy_areas.get(self.key(period), [])

    def kpis_by_score_range(self, organization_id, period):
        self.check()
        return [{"trans_name": "All", "kpis": self.kpis.get((str(organization_id), self.key(period)), [])}]

    def kpi_detail(self, kpi_id, organization_id):
        self.check()
        if str(kpi_id) not in ("1", "2", "3", "4"):
            return None
        row = next(row for row in self.kpis[("312", "2019-1")] if str(row["id"]) == str(kpi_id))
        return {**row, "records": [
            {"ethio_date": "2018-04", "record_type": "quarterly", "target": "90", "performance": "80", "score": 80.0},
            {"ethio_date": "2018", "record_type": "yearly", "target": "90", "performance": "92", "score": 100.0},
            {"ethio_date": "2018-01", "record_type": "quarterly", "target": "88", "performance": "70", "score": 75.0},
        ]}


INDICATOR = {
    "id": 7104, "title_ENG": "GDP Growth", "title_AMH": "ጂዲፒ", "code": "EG-GDPCP-01", "measurement_units": "%",
    "kpi_characteristics": "inc", "latest_data": "annual", "quarter_data": [], "month_data": [],
    "annual_data": [{"for_datapoint": "2016", "performance": 8.0}, {"for_datapoint": "2017", "performance": None},
                    {"for_datapoint": "2018", "performance": 10.0}],
}


class PreferencesTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.dpmes = FakeDPMES()
        patches = [
            patch.object(dpmes_client, "is_configured", return_value=True),
            patch.object(dpmes_client, "current_ethiopian_year", return_value=self.dpmes.year),
            patch.object(dpmes_client, "score_ranges", return_value=RANGES),
            patch.object(dpmes_client, "child_organizations", side_effect=self.dpmes.child_organizations),
            patch.object(dpmes_client, "policy_area_scores", side_effect=self.dpmes.policy_area_scores),
            patch.object(dpmes_client, "kpis_by_score_range", side_effect=self.dpmes.kpis_by_score_range),
            patch.object(dpmes_client, "kpi_detail", side_effect=self.dpmes.kpi_detail),
            patch.object(time_series_client, "indicator_detail",
                         side_effect=lambda identifier: INDICATOR if str(identifier) == "7104" else None),
            patch.object(time_series_client, "search", return_value=[
                {"id": 58, "name_ENG": "Economic Growth", "indicators": [INDICATOR]},
            ]),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

        ministry = Ministry.objects.create(name="Ministry of Health", abbreviation="MoH", dpmes2_id=312)
        users = get_user_model().objects
        self.user = users.create_user(email="a@example.com", username="a", password="Str0ng!Pass", ministry=ministry)
        self.other = users.create_user(email="b@example.com", username="b", password="Str0ng!Pass", ministry=ministry)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def follow(self, kind, identifier, **extra):
        return self.client.post("/api/preferences/follows/", {"kind": kind, "id": identifier, **extra}, format="json")


class PeriodTests(PreferencesTestCase):
    def test_quarter_is_the_newest_one_with_scores_against_the_one_before(self):
        current, previous = sources.periods("quarter")
        self.assertEqual(current, {"year": 2019, "quarter": 1})
        self.assertEqual(previous, {"year": 2018, "quarter": 4})

    def test_year_is_the_last_complete_year_against_the_one_before(self):
        self.assertEqual(sources.periods("year"), ({"year": 2018}, {"year": 2017}))

    def test_scores_are_read_once_and_then_served_from_the_cache(self):
        sources.organizations({"year": 2018})
        sources.organizations({"year": 2018})
        self.assertEqual(dpmes_client.child_organizations.call_count, 1)


class HelperTests(SimpleTestCase):
    def test_direction_reads_both_services_spellings(self):
        self.assertEqual(sources.direction("Increasing"), "increasing")
        self.assertEqual(sources.direction("dec"), "decreasing")
        self.assertEqual(sources.direction(None), "")

    def test_band_is_the_highest_one_starting_at_or_below_the_score(self):
        bands = [{"name": "Low", "start": 0.0}, {"name": "Mid", "start": 50.0}, {"name": "High", "start": 95.0}]
        self.assertEqual(sources.band_for(49.999, bands)["name"], "Low")
        self.assertEqual(sources.band_for(50, bands)["name"], "Mid")
        self.assertEqual(sources.band_for(100, bands)["name"], "High")
        self.assertIsNone(sources.band_for(-1, bands))

    def test_new_sections_are_added_after_the_saved_order(self):
        preference = UserPreference(sections=[{"key": "movers", "visible": False}, {"key": "gone", "visible": True}])
        ordered = preference.ordered_sections()
        self.assertEqual(ordered[0], {"key": "movers", "visible": False})
        self.assertEqual([entry["key"] for entry in ordered[1:]], [key for key in SECTIONS if key != "movers"])
        self.assertFalse(preference.shows("movers"))
        self.assertTrue(preference.shows("topics"))


class PreferenceApiTests(PreferencesTestCase):
    url = "/api/preferences/"

    def test_requires_sign_in(self):
        for path in ("", "follows/", "options/?kind=organization", "dashboard/", "movers/"):
            # 403 from session auth (website), 401 from JWT (app): either way, refused.
            self.assertIn(APIClient().get(self.url + path).status_code, (401, 403), path)

    def test_defaults_are_returned_without_saving_anything(self):
        data = self.client.get(self.url).json()["data"]
        self.assertEqual(data["period"], "quarter")
        self.assertEqual(data["movers_limit"], 5)
        self.assertEqual([entry["key"] for entry in data["sections"]], list(SECTIONS))
        self.assertFalse(UserPreference.objects.exists())

    def test_saves_only_the_fields_sent(self):
        response = self.client.put(self.url, {
            "period": "year", "sections": [{"key": "movers", "visible": False}, {"key": "pinned_kpis"}],
        }, format="json")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["period"], "year")
        self.assertEqual(data["movers_direction"], "both")
        self.assertEqual(data["sections"][:2], [{"key": "movers", "visible": False},
                                                {"key": "pinned_kpis", "visible": True}])
        self.assertEqual(len(data["sections"]), len(SECTIONS))
        self.assertEqual(UserPreference.objects.get(user=self.user).period, "year")

    def test_rejects_unknown_sections_repeats_and_out_of_range_values(self):
        for body in ({"sections": [{"key": "nope"}]},
                     {"sections": [{"key": "movers"}, {"key": "movers"}]},
                     {"movers_limit": 0}, {"period": "week"}):
            response = self.client.put(self.url, body, format="json")
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")


class FollowApiTests(PreferencesTestCase):
    def test_follow_takes_the_name_from_the_source_service(self):
        response = self.follow("organization", "313")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual((data["id"], data["name"], data["code"]), ("313", "Ministry of Peace", "MoP"))
        self.assertEqual(Follow.objects.get(pk=data["follow_id"]).name_am, "Ministry of Peace (am)")

    def test_following_twice_returns_the_same_record(self):
        first = self.follow("policy_area", "47").json()["data"]["follow_id"]
        second = self.follow("policy_area", "47")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["data"]["follow_id"], first)
        self.assertEqual(Follow.objects.count(), 1)

    def test_kpi_defaults_to_the_users_own_organization(self):
        data = self.follow("kpi", "1").json()["data"]
        self.assertEqual((data["organization_id"], data["name"]), ("312", "Ambulance response"))

    def test_indicator_is_checked_against_the_time_series_service(self):
        self.assertEqual(self.follow("indicator", "7104").json()["data"]["name"], "GDP Growth")
        self.assertEqual(self.follow("indicator", "1").status_code, 404)

    def test_unknown_items_and_kinds_are_rejected(self):
        self.assertEqual(self.follow("organization", "999").json()["error"]["code"], "ITEM_NOT_FOUND")
        self.assertEqual(self.follow("kpi", "999").status_code, 404)
        self.assertEqual(self.follow("goal", "1").status_code, 400)
        self.assertEqual(Follow.objects.count(), 0)

    def test_follow_fails_cleanly_when_the_source_is_down(self):
        self.dpmes.down = True
        response = self.follow("organization", "313")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "UPSTREAM_ERROR")

    def test_limit_per_kind(self):
        with patch.object(Follow, "LIMIT_PER_KIND", 1):
            self.assertEqual(self.follow("organization", "312").status_code, 201)
            response = self.follow("organization", "313")
        self.assertEqual(response.json()["error"]["code"], "FOLLOW_LIMIT_REACHED")

    def test_list_filter_and_unfollow_are_limited_to_the_user(self):
        mine = self.follow("organization", "313").json()["data"]["follow_id"]
        self.follow("policy_area", "47")
        theirs = Follow.objects.create(user=self.other, kind="organization", external_id="312", name="x")

        rows = self.client.get("/api/preferences/follows/?kind=organization").json()["data"]
        self.assertEqual([row["follow_id"] for row in rows], [mine])
        self.assertEqual(self.client.delete(f"/api/preferences/follows/{theirs.pk}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/preferences/follows/{mine}/").status_code, 200)
        self.assertEqual(Follow.objects.filter(user=self.user).count(), 1)
        self.assertTrue(Follow.objects.filter(pk=theirs.pk).exists())

    def test_reorder(self):
        ids = [self.follow("organization", value).json()["data"]["follow_id"] for value in ("312", "313", "314")]
        url = "/api/preferences/follows/order/"
        response = self.client.put(url, {"kind": "organization", "follow_ids": [ids[2], ids[0]]}, format="json")
        self.assertEqual([row["follow_id"] for row in response.json()["data"]], [ids[2], ids[0], ids[1]])
        listed = self.client.get("/api/preferences/follows/").json()["data"]
        self.assertEqual([row["follow_id"] for row in listed], [ids[2], ids[0], ids[1]])

        theirs = Follow.objects.create(user=self.other, kind="organization", external_id="312", name="x")
        for wrong in ([ids[0], ids[0]], [theirs.pk]):
            response = self.client.put(url, {"kind": "organization", "follow_ids": wrong}, format="json")
            self.assertEqual(response.status_code, 400)


class OptionTests(PreferencesTestCase):
    url = "/api/preferences/options/"

    def test_organizations_are_searchable_and_marked_when_followed(self):
        self.follow("organization", "313")
        rows = self.client.get(self.url, {"kind": "organization", "search": "ministry p"}).json()["data"]
        self.assertEqual([(row["id"], row["followed"]) for row in rows], [("313", True)])
        self.assertEqual(len(self.client.get(self.url, {"kind": "organization"}).json()["data"]), 3)

    def test_kpis_come_from_the_users_organization(self):
        rows = self.client.get(self.url, {"kind": "kpi"}).json()["data"]
        self.assertEqual([(row["id"], row["organization_id"]) for row in rows], [("1", "312")])

    def test_indicators_need_a_search(self):
        self.assertEqual(self.client.get(self.url, {"kind": "indicator"}).json()["data"], [])
        rows = self.client.get(self.url, {"kind": "indicator", "search": "gdp"}).json()["data"]
        self.assertEqual([(row["id"], row["category"]) for row in rows], [("7104", "Economic Growth")])

    def test_kind_is_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"kind": "goal"}).status_code, 400)


class MoverTests(PreferencesTestCase):
    url = "/api/preferences/movers/"

    def get(self, **params):
        return self.client.get(self.url, params).json()["data"]

    def test_kpis_are_ranked_by_change_in_score_and_unreported_ones_left_out(self):
        data = self.get()
        self.assertEqual(data["period"]["current"]["label"], "2019 Q1")
        self.assertEqual(data["period"]["previous"]["label"], "2018 Q4")
        self.assertEqual([(row["name"], row["change"]) for row in data["rising"]],
                         [("Ambulance response", 20.0), ("Clinic visits", 10.0)])
        self.assertEqual([(row["name"], row["change"]) for row in data["declining"]], [("Maternal deaths", -50.0)])
        self.assertEqual(data["rising"][0]["organization"], "Ministry of Health")

    def test_direction_and_limit(self):
        data = self.get(direction="rising", limit=1)
        self.assertEqual(len(data["rising"]), 1)
        self.assertEqual(data["declining"], [])

    def test_categories_average_the_kpis_reported_in_both_periods(self):
        data = self.get(kind="category")
        by_name = {row["name"]: row for row in data["rising"] + data["declining"]}
        self.assertEqual(by_name["Emergency care"]["change"], 20.0)   # KPI 4 has no result this quarter
        self.assertEqual(by_name["Emergency care"]["kpi_count"], 1)
        self.assertEqual(by_name["Maternal health"]["score"], 55.0)   # (40 + 70) / 2
        self.assertEqual(by_name["Maternal health"]["change"], -20.0)  # from (90 + 60) / 2

    def test_an_organization_with_nothing_reported_is_not_a_decline(self):
        data = self.get(kind="organization")
        self.assertEqual([row["code"] for row in data["rising"]], ["MoP"])
        self.assertEqual([row["code"] for row in data["declining"]], ["MoH"])   # not MoWE, which scored 0

    def test_following_scope_and_yearly_period(self):
        self.follow("organization", "313")
        data = self.get(kind="organization", scope="following", period="year")
        self.assertEqual(data["period"]["current"]["label"], "2018")
        self.assertEqual([(row["code"], row["change"]) for row in data["rising"]], [("MoP", 4.0)])
        self.assertEqual(data["declining"], [])

    def test_defaults_come_from_the_saved_preferences(self):
        self.client.put("/api/preferences/", {"movers_direction": "declining", "movers_limit": 1}, format="json")
        data = self.get()
        self.assertEqual((data["rising"], len(data["declining"])), ([], 1))

    def test_bad_parameters_and_a_source_failure(self):
        for params in ({"kind": "goal"}, {"limit": "0"}, {"limit": "many"}, {"period": "week"}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400, params)
        self.dpmes.down = True
        self.assertEqual(self.client.get(self.url).status_code, 502)


class DashboardTests(PreferencesTestCase):
    url = "/api/preferences/dashboard/"

    def get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_a_new_user_sees_their_own_organization(self):
        data = self.get()
        self.assertFalse(data["has_follows"])
        self.assertEqual(data["errors"], {})
        self.assertEqual(data["period"]["type"], "quarter")
        (row,) = data["organizations"]
        self.assertEqual((row["id"], row["is_default"], row["follow_id"]), ("312", True, None))
        self.assertEqual((row["score"], row["previous_score"], row["change"]), (70.0, 80.0, -10.0))
        self.assertEqual((row["rank"], row["ranked_total"]), (2, 2))
        self.assertEqual(row["band"]["name"], "In Progress")
        self.assertEqual(data["movers"]["kpis"]["declining"][0]["name"], "Maternal deaths")
        self.assertEqual([entry["key"] for entry in data["sections"]], list(SECTIONS))

    def test_followed_items_replace_the_default_and_keep_their_order(self):
        second = self.follow("organization", "313").json()["data"]["follow_id"]
        first = self.follow("organization", "312").json()["data"]["follow_id"]
        self.client.put("/api/preferences/follows/order/",
                        {"kind": "organization", "follow_ids": [first, second]}, format="json")
        self.follow("policy_area", "47")
        self.follow("kpi", "2")
        self.follow("kpi", "4")
        self.follow("indicator", "7104")

        data = self.get()
        self.assertTrue(data["has_follows"])
        self.assertEqual([(row["id"], row["is_default"]) for row in data["organizations"]],
                         [("312", False), ("313", False)])
        self.assertEqual([(row["name"], row["change"]) for row in data["policy_areas"]], [("Macroeconomy", -15.0)])

        maternal, unreported = data["kpis"]
        self.assertEqual((maternal["score"], maternal["change"], maternal["band"]["name"]),
                         (40.0, -50.0, "Requires Intervention"))
        self.assertEqual([point["period"] for point in maternal["history"]], ["2018 Q1", "2018 Q4", "2018"])
        self.assertFalse(unreported["has_data"])
        self.assertIsNone(unreported["band"])

        (indicator,) = data["indicators"]
        self.assertEqual((indicator["latest"], indicator["previous"]),
                         ({"period": "2018", "value": 10.0}, {"period": "2016", "value": 8.0}))
        self.assertEqual((indicator["change"], indicator["change_percent"], indicator["direction"]),
                         (2.0, 25.0, "increasing"))

        attention = [(item["kind"], item["name"], item["reason"]) for item in data["needs_attention"]]
        self.assertEqual(attention, [("kpi", "Not reported", "no_data"),
                                     ("policy_area", "Macroeconomy", "low_score"),
                                     ("kpi", "Maternal deaths", "low_score")])

    def test_hidden_sections_are_not_built(self):
        self.client.put("/api/preferences/", {"sections": [
            {"key": "movers", "visible": False}, {"key": "needs_attention", "visible": False},
        ]}, format="json")
        data = self.get()
        self.assertIsNone(data["movers"])
        self.assertEqual(data["needs_attention"], [])

    def test_a_failing_service_only_empties_its_own_sections(self):
        self.follow("indicator", "7104")
        self.dpmes.down = True
        cache.clear()
        data = self.get()
        self.assertEqual(data["indicators"][0]["name"], "GDP Growth")
        self.assertEqual(set(data["errors"]), {"organizations", "policy_areas", "kpis", "movers"})
        self.assertEqual(data["errors"]["kpis"]["code"], "UPSTREAM_ERROR")
        self.assertIsNone(data["period"])

    @override_settings(DPMES2_API_KEY="")
    def test_missing_key_is_reported_as_not_configured(self):
        dpmes_client.is_configured.return_value = False
        self.assertEqual(self.get()["errors"]["organizations"]["code"], "DPMES2_NOT_CONFIGURED")
        self.assertEqual(self.client.get("/api/preferences/movers/").status_code, 503)

    def test_a_pinned_kpi_survives_its_history_failing_to_load(self):
        self.follow("kpi", "2")
        with patch.object(dashboard.sources, "kpi", side_effect=sources.SourceError("down")):
            (row,) = self.get()["kpis"]
        self.assertEqual((row["score"], row["history"]), (40.0, []))
