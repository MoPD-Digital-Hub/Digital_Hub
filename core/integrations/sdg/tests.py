import json
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from integrations.sdg import client, series


def page(props):
    body = json.dumps({"props": {"pageProps": props}, "buildId": "abc"})
    return f'<html><script id="__NEXT_DATA__" type="application/json">{body}</script></html>'


GOAL_PROPS = {
    "countryName": "Ethiopia",
    "data": {"sdg": {
        "goals": [{"id": "1", "goal": "No poverty"}, {"id": "2", "goal": "Zero hunger"}],
        "targets": [{"id": "1.1", "goal": "1", "description": "Eradicate extreme poverty"}],
        "indicators": [{"id": "1.1.1", "goal": "1", "description": "Poverty", "data": None}],
    }},
}


def point(year, value, unit="Percent"):
    return {"year": year, "value": str(value), "unit": unit}


def raw_series(values, **dims):
    return {"disaggregations": [{"type": t, "value": v} for t, v in dims.items()],
            "data": {str(y): point(y, v) for y, v in values.items()}}


class ClientTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("integrations.sdg.client.requests.get")
    def test_reads_the_data_embedded_in_the_goal_page(self, get):
        get.return_value = Mock(text=page(GOAL_PROPS), raise_for_status=Mock())
        goal = client.goal(1)
        self.assertEqual(goal["goal"]["goal"], "No poverty")
        self.assertEqual(len(goal["goals"]), 2)
        self.assertEqual([t["id"] for t in goal["targets"]], ["1.1"])
        self.assertEqual(get.call_args.args[0], "https://sdg.mopd.gov.et/goals/sdg/1/")
        client.goal(1)
        self.assertEqual(get.call_count, 1, "a second read comes from the cache")

    @patch("integrations.sdg.client.requests.get")
    def test_failures_raise_sdg_error(self, get):
        get.side_effect = requests.ConnectionError("down")
        with self.assertRaises(client.SDGError):
            client.goal(3)
        get.side_effect = None
        get.return_value = Mock(text="<html>no data</html>", raise_for_status=Mock())
        with self.assertRaises(client.SDGError):
            client.goal(4)


class SeriesTests(SimpleTestCase):
    def test_headline_keeps_national_totals_and_category_series(self):
        data = [
            raw_series({2011: 29.6, 2016: 23.5}, **{"Poverty Type": "Absolute poverty", "Region": "NATIONAL"}),
            raw_series({2011: 33.6, 2016: 24.8}, **{"Poverty Type": "Food Poverty", "Region": "NATIONAL"}),
            raw_series({2016: 27}, **{"Poverty Type": "Absolute poverty", "Region": "Tigray"}),
        ]
        shown, notes = series.select(data)
        self.assertEqual([s["name"] for s in shown], ["Absolute poverty", "Food Poverty"])
        self.assertEqual(shown[0]["dimension"], "Poverty Type")
        self.assertEqual(shown[0]["points"], [{"year": 2011, "value": 29.6}, {"year": 2016, "value": 23.5}])
        self.assertEqual(shown[0]["unit"], "%")
        self.assertEqual(notes, [])

    def test_breakdown_shows_one_dimension_with_its_total_last(self):
        data = [
            raw_series({2016: 19}, Region="NATIONAL", Sex="BOTH SEX"),
            raw_series({2016: 27}, Region="Tigray", Sex="BOTH SEX"),
            raw_series({2016: 20.7}, Region="SNNP", Sex="BOTH SEX"),
            raw_series({2016: 25}, Region="Tigray", Sex="FEMALE"),
        ]
        shown, _ = series.select(data, "region")
        self.assertEqual([s["name"] for s in shown], ["Tigray", "SNNP", "National"])
        self.assertEqual(shown[0]["dimension"], "Region")

    def test_missing_breakdown_is_noted(self):
        shown, notes = series.select([raw_series({2020: 5})], "sex")
        self.assertEqual([s["name"] for s in shown], ["Total"])
        self.assertIn("no breakdown by sex", notes[0])

    def test_non_numeric_values_are_dropped(self):
        data = [{"disaggregations": [], "data": {"2019": point(2019, "n/a"), "2020": point(2020, "1,200")}}]
        shown, _ = series.select(data)
        self.assertEqual(shown[0]["points"], [{"year": 2020, "value": 1200}])
