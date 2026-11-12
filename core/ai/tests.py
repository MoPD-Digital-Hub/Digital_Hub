import json
from unittest.mock import AsyncMock, patch

import numpy as np
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from ai.engine import catalog, planner, render, verify
from ai.engine.catalog import CatalogIndex, Match
from ai.engine.llm import LLMError
from ai.models import AnswerTrace, CatalogEntity, ChatInstance, QuestionHistory


def entity(kind, external_id, name, code="", context="", aliases=(), vector=(1.0, 0.0)):
    vec = np.asarray(vector, dtype="<f4")
    return CatalogEntity(kind=kind, external_id=external_id, code=code, name=name, context=context,
                         aliases=list(aliases), embedding=(vec / np.linalg.norm(vec)).tobytes())


class CatalogBuildTests(SimpleTestCase):
    def test_indicator_rows_walk_children_and_skip_uncoded(self):
        topics = [{"title_ENG": "Macro", "categories": [{"name_ENG": "Growth", "indicators": [
            {"title_ENG": "GDP Growth", "code": "EG-01", "children": [
                {"title_ENG": "Grouping", "code": "", "children": [{"title_ENG": "Industry growth", "code": "EG-IND"}]},
            ]},
        ]}]}]
        rows = {r["code"]: r for r in catalog._indicator_rows(topics)}
        self.assertEqual(sorted(rows), ["EG-01", "EG-IND"])
        self.assertEqual(rows["EG-IND"]["details"]["parent"], "Grouping")
        self.assertTrue(rows["EG-01"]["search_text"].startswith("GDP Growth\n"))

    def test_misspelled_dpmes_names_get_a_corrected_alias(self):
        rows = catalog._dpmes_rows(
            [{"id": 7, "name": "Minsitry of Education", "code": "MoE"}], {7: {"policy_areas": []}}, [], {})
        self.assertIn("Ministry of Education", rows[0]["aliases"])


    def test_planning_ministry_answers_to_its_new_name(self):
        rows = catalog._dpmes_rows(
            [{"id": 9, "name": "Ministry of Planning and Development", "code": "MoPD"}], {9: {"policy_areas": []}}, [], {})
        self.assertIn("Ministry of National Strategy", rows[0]["aliases"])
        self.assertIn("MoNS", rows[0]["aliases"])


class CatalogSyncTests(TestCase):
    def test_alias_changes_are_saved_without_re_embedding(self):
        row = {"kind": CatalogEntity.ORGANIZATION, "external_id": "9", "code": "MoPD", "name": "Ministry X",
               "name_am": "", "aliases": ["MoPD"], "context": "", "details": {}, "search_text": "Ministry X"}

        def run(rows):
            embed = lambda texts: [np.array([1.0, 0.0])] * len(texts)
            with patch.object(catalog.time_series_client, "fetch_topics", return_value=[]), \
                    patch.object(catalog, "_indicator_rows", return_value=[dict(r) for r in rows]), \
                    patch.object(catalog.llm, "embed_documents", side_effect=embed) as embedded:
                return catalog.sync(include_dpmes=False, include_sdg=False, log=lambda *_: None), embedded.call_count

        self.assertEqual(run([row])[0]["created"], 1)
        counts, embeds = run([{**row, "aliases": ["MoPD", "MoNS"]}])
        self.assertEqual((counts["updated"], embeds), (1, 0))
        self.assertEqual(CatalogEntity.objects.get(external_id="9").aliases, ["MoPD", "MoNS"])
        self.assertEqual(run([{**row, "aliases": ["MoPD", "MoNS"]}])[0]["unchanged"], 1)

class CatalogResolveTests(SimpleTestCase):
    def setUp(self):
        rows = [
            entity(CatalogEntity.INDICATOR, "U-1", "Urban Unemployment", "U-1", "category: Labour", vector=(0.9, 0.1)),
            entity(CatalogEntity.INDICATOR, "U-2", "National Unemployment", "U-2", "category: Labour", vector=(0.8, 0.2)),
            entity(CatalogEntity.INDICATOR, "G-1", "GDP Growth", "G-1", "category: Growth", vector=(0.1, 0.9)),
            entity(CatalogEntity.INDICATOR, "G-2", "Crop Contribution to GDP Growth", "G-2", "category: Growth", vector=(0.15, 0.9)),
        ]
        for i, row in enumerate(rows, start=1):
            row.id = i
        self.index = CatalogIndex(rows)
        patcher = patch.object(CatalogIndex, "get", return_value=self.index)
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, text, vector):
        with patch("ai.engine.catalog.llm.embed_query", return_value=np.asarray(vector, dtype="<f4") / np.linalg.norm(vector)):
            return async_to_sync(catalog.resolve)(text, CatalogEntity.INDICATOR)

    def test_exact_code_wins_without_embedding(self):
        with patch("ai.engine.catalog.llm.embed_query") as embed:
            match = async_to_sync(catalog.resolve)("g-1", CatalogEntity.INDICATOR)[0]
        embed.assert_not_called()
        self.assertEqual((match.name, match.method), ("GDP Growth", "exact"))

    def test_word_overlap_beats_a_closer_embedding(self):
        # The embedding prefers Urban; the words say National.
        self.assertEqual(self.resolve("national unemployment rate", (0.9, 0.1))[0].name, "National Unemployment")

    def test_name_precision_prefers_the_plain_indicator(self):
        self.assertEqual(self.resolve("GDP growth", (0.12, 0.9))[0].name, "GDP Growth")

    def test_misspelling_snaps_to_catalog_word(self):
        self.assertEqual(self.resolve("nationl unemploymant", (0.85, 0.15))[0].name, "National Unemployment")


class RenderTests(SimpleTestCase):
    def test_series_table_and_chart_read_oldest_to_newest(self):
        html = render.sections([{"tool": "indicator_series", "data": {
            "indicator": {"name": "GDP Growth", "unit": "%"},
            "series": {"annual": [{"period": "2016", "value": 8.05}, {"period": "2017", "value": 9.2}]},
        }}])
        chart = json.loads(html.split("<chart-data>")[1].split("</chart-data>")[0])
        self.assertEqual(chart["labels"], ["2016", "2017"])
        self.assertEqual(chart["data"], [8.05, 9.2])
        self.assertLess(html.index("<table>"), html.index("<chart-data>"))

    def test_organization_score_adds_detail_button_with_legacy_quarter(self):
        html = render.sections([{"tool": "organization_score", "title": "MoH", "period": "2018 EC Q2", "data": {
            "organization": {"id": "312", "name": "Ministry of Health"}, "period": {"year": 2018, "quarter": 2},
            "score": {"value": 66.65, "color": "#FFBF00", "band": "In Progress"},
            "policy_areas": [{"name": "Health", "value": 66.65, "color": "#FFBF00"}],
        }}])
        blocks = [json.loads(b.split("</chart-data>")[0]) for b in html.split("<chart-data>")[1:]]
        self.assertEqual(blocks[-1], {"type": "button", "button_type": "ministry_detail", "id": "312",
                                      "year": "2018", "quarter": "6month"})

    def test_names_are_escaped(self):
        html = render.sections([{"tool": "rank_organizations", "title": "t", "period": "p", "data": {
            "items": [{"name": "</chart-data><script>x</script>", "value": 1.0, "color": None}]}}])
        self.assertNotIn("<script>", html)
        self.assertEqual(html.count("</chart-data>"), 1)
        chart = json.loads(html.split("<chart-data>")[1].split("</chart-data>")[0])
        self.assertEqual(chart["labels"], ["</chart-data><script>x</script>"])


SDG_FEED = {
    "goal": {"id": "1", "goal": "No poverty", "description": "End poverty"},
    "targets": [{"id": "1.1", "description": "Eradicate extreme poverty"}],
    "indicators": [
        {"id": "1.1.1", "goal": "1", "target": "1.1", "type": "Global", "description": "Population below the poverty line",
         "data": None, "sources": [], "providers": []},
        {"id": "1.1.1P1", "goal": "1", "target": "1.1", "type": "Proxy", "parentIndicator": "1.1.1",
         "description": "Poverty headcount index", "sources": ["HICE survey 2015/16"], "providers": ["NPC, MoPD"],
         "data": [
             {"disaggregations": [{"type": "Region", "value": "NATIONAL"}],
              "data": {"2011": {"year": 2011, "value": "29.6", "unit": "Index"},
                       "2016": {"year": 2016, "value": "23.5", "unit": "Index"}}},
             {"disaggregations": [{"type": "Region", "value": "Tigray"}],
              "data": {"2016": {"year": 2016, "value": "27", "unit": "Index"}}},
         ]},
        # The platform lists a few indicators twice; the copy with data wins.
        {"id": "1.1.1P1", "goal": "1", "target": "1.1", "description": "Poverty headcount index", "data": None},
    ],
}


class SDGTests(SimpleTestCase):
    def test_catalog_rows_cover_goals_and_indicators_once(self):
        rows = catalog._sdg_rows([SDG_FEED])
        goals = [r for r in rows if r["kind"] == CatalogEntity.SDG_GOAL]
        indicators = {r["code"]: r for r in rows if r["kind"] == CatalogEntity.SDG_INDICATOR}
        self.assertEqual(goals[0]["code"], "SDG 1")
        self.assertIn("Goal 1", goals[0]["aliases"])
        self.assertEqual(sorted(indicators), ["1.1.1", "1.1.1P1"])
        self.assertTrue(indicators["1.1.1P1"]["details"]["has_data"])
        self.assertIn("proxy for indicator 1.1.1", indicators["1.1.1P1"]["context"])

    def run_indicator(self, code, **args):
        from ai.engine import tools

        match = Match(1, CatalogEntity.SDG_INDICATOR, code, code, "x", 1.0, "exact", {"goal": "1"})
        with patch.object(tools.sdg_client, "goal", return_value=SDG_FEED):
            return tools.sdg_indicator(sdg_indicator=match, **args)

    def test_indicator_without_data_answers_with_its_proxy(self):
        result = self.run_indicator("1.1.1")
        self.assertEqual(result["data"]["indicator"]["code"], "1.1.1P1")
        self.assertIn("proxy indicator 1.1.1P1", result["notes"][0])
        self.assertEqual(result["calendar"], "Gregorian")
        self.assertEqual(result["source"], "Ethiopia's national SDG platform")
        self.assertEqual(result["original_data"], "HICE survey 2015/16, NPC, MoPD")
        self.assertEqual([s["name"] for s in result["data"]["series"]], ["Total"])

    def test_breakdown_shows_regions_as_columns_and_names_the_source(self):
        result = self.run_indicator("1.1.1P1", breakdown="region", year=2016)
        self.assertEqual(result["data"]["requested"]["values"][0], {"series": "Tigray", "value": 27})
        html = render.sections([result])
        self.assertIn("<th>Year</th><th>Tigray (Index)</th><th>National (Index)</th>", html)
        chart = json.loads(html.split("<chart-data>")[1].split("</chart-data>")[0])
        self.assertEqual([s["name"] for s in chart["series"]], ["Tigray", "National"])
        self.assertTrue(html.endswith('<p class="ai-source" data-source="sdg" data-sdg-goal="1">Source: '
                                      "Ethiopia&#x27;s national SDG platform "
                                      "(sdg.mopd.gov.et; original data: HICE survey 2015/16, NPC, MoPD)</p>"))

    def test_many_series_render_one_row_each_with_their_latest_value(self):
        regions = ["Tigray", "Afar", "Amhara", "Oromia", "Somali"]
        result = {"tool": "sdg_indicator", "title": "Stunting: SDG 2.2.1a", "period": "2023", "data": {
            "indicator": {"name": "Stunting", "unit": "%"}, "breakdown": None,
            "series": [{"name": r, "dimension": "Region", "unit": "%", "points": [{"year": 2023, "value": 30 + i}]}
                       for i, r in enumerate(regions)]}}
        html = render.sections([result])
        self.assertIn("<th>Region</th><th>Latest value (%)</th><th>Year</th>", html)
        self.assertIn("<td>Somali</td><td>34</td><td>2023</td>", html)
        chart = json.loads(html.split("<chart-data>")[1].split("</chart-data>")[0])
        self.assertEqual((chart["type"], chart["labels"]), ("bar", regions))

    def test_single_series_renders_years_as_rows_with_a_line_chart(self):
        html = render.sections([self.run_indicator("1.1.1P1")])
        self.assertIn("<th>Year</th><th>Value (Index)</th>", html)
        chart = json.loads(html.split("<chart-data>")[1].split("</chart-data>")[0])
        self.assertEqual((chart["labels"], chart["data"]), (["2011", "2016"], [29.6, 23.5]))
        self.assertNotIn("series", chart)

    def test_goal_overview_lists_the_latest_national_value(self):
        from ai.engine import tools

        match = Match(1, CatalogEntity.SDG_GOAL, "1", "SDG 1", "No poverty", 1.0, "exact")
        with patch.object(tools.sdg_client, "goal", return_value=SDG_FEED):
            result = tools.sdg_goal(sdg_goal=match)
        self.assertEqual(result["data"]["indicators"], [{
            "code": "1.1.1P1", "name": "Poverty headcount index", "series": None, "value": 23.5, "unit": "Index",
            "year": 2016}])
        html = render.sections([result])
        self.assertIn("<td>1.1.1P1 Poverty headcount index</td><td>23.5</td><td>Index</td><td>2016</td>", html)
        self.assertIn('data-sdg-goal="1"', html)

    def test_only_sdg_results_carry_a_goal_number(self):
        self.assertEqual(render._sdg_goal_number({"tool": "sdg_indicator", "data": {"indicator": {"code": "16.2.1"}}}),
                         "16")
        self.assertEqual(render._sdg_goal_number({"tool": "sdg_indicator", "data": {"indicator": {"code": "x"}}}), "")
        self.assertEqual(render._sdg_goal_number({"tool": "sdg_goal", "data": {"goal": {"id": "18"}}}), "")
        self.assertEqual(render._sdg_goal_number({"tool": "indicator_series", "data": {}}), "")

    def test_unreachable_platform_is_a_tool_error(self):
        from ai.engine import tools
        from integrations.sdg.client import SDGError

        match = Match(1, CatalogEntity.SDG_GOAL, "1", "SDG 1", "No poverty", 1.0, "exact")
        with patch.object(tools.sdg_client, "goal", side_effect=SDGError("down")), \
                self.assertRaises(tools.ToolError):
            tools.sdg_goal(sdg_goal=match)


class VerifyTests(SimpleTestCase):
    RESULTS = [{"data": {"series": {"annual": [{"period": "2018", "value": 7.7}, {"period": "2007", "value": 10.41}]}}}]

    def test_numbers_from_the_data_pass(self):
        self.assertEqual(verify.unsupported_numbers("<p>7.7% in 2018 EC, down from 10.41</p>", self.RESULTS), [])

    def test_invented_numbers_are_flagged(self):
        self.assertEqual(verify.unsupported_numbers("<p>It reached 12.5% in 2018</p>", self.RESULTS), [12.5])

    def test_style_colours_and_small_counts_are_ignored(self):
        html = '<p><span style="color: #FF7259">3 areas</span> scored 7.7</p>'
        self.assertEqual(verify.unsupported_numbers(html, self.RESULTS), [])

    def test_missing_years_inside_the_series_are_not_flagged(self):
        self.assertEqual(verify.unsupported_numbers("<p>Figures for 2012 and 2015 are unavailable.</p>", self.RESULTS), [])
        self.assertEqual(verify.unsupported_numbers("<p>It will reach 9.1 by 2030.</p>", self.RESULTS), [9.1, 2030.0])

    def test_foreign_script_is_detected(self):
        self.assertTrue(verify.foreign_script("<p>የጤናစောင့်leት</p>"))
        self.assertFalse(verify.foreign_script("<p>የጤና ሚኒስቴር 66.65 (In Progress) ነው።</p>"))


class PlannerTests(SimpleTestCase):
    def test_calls_missing_a_required_entity_are_dropped(self):
        calls = planner._clean_calls([
            {"tool": "indicator_series"},
            {"tool": "indicator_series", "indicator": "GDP growth", "year": None},
            {"tool": "no_such_tool", "indicator": "x"},
            {"tool": "rank_organizations", "order": "bottom"},
        ])
        self.assertEqual(calls, [{"tool": "indicator_series", "indicator": "GDP growth"},
                                 {"tool": "rank_organizations", "order": "bottom"}])

    def test_data_plan_without_usable_calls_becomes_general(self):
        with patch("ai.engine.planner.llm.json_completion", return_value={"kind": "data", "calls": [{"tool": "indicator_series"}]}):
            plan = async_to_sync(planner.plan)("growth?")
        self.assertEqual((plan.kind, plan.calls), ("general", []))

    def test_language_comes_from_the_script(self):
        with patch("ai.engine.planner.llm.json_completion", return_value={"kind": "greeting", "calls": []}):
            self.assertEqual(async_to_sync(planner.plan)("ሰላም").language, "Amharic")


def fake_stream(*pieces):
    async def stream(*args, **kwargs):
        for piece in pieces:
            yield piece
    return stream


GDP = Match(1, CatalogEntity.INDICATOR, "EG-01", "EG-01", "GDP Growth", 0.9, "semantic")
SERIES = {"tool": "indicator_series", "title": "GDP Growth", "source": "MoPD", "notes": [], "data": {
    "indicator": {"name": "GDP Growth", "unit": "%"}, "series": {"annual": [{"period": "2018", "value": 7.7}]}}}


class PipelineTests(TestCase):
    def run_pipeline(self, question="What is GDP growth?", instance=None):
        from ai.engine.pipeline import answer_stream

        async def collect():
            return [event async for event in answer_stream(question, instance=instance)]
        return async_to_sync(collect)()

    @patch("ai.engine.pipeline.compose.stream", fake_stream("<p>GDP grew ", "7.7% in 2018 EC.</p>"))
    @patch("ai.engine.pipeline.catalog.resolve", return_value=[GDP])
    @patch("ai.engine.pipeline.planner.plan")
    def test_events_stream_then_done_without_repeating_the_answer(self, mock_plan, _resolve):
        from ai.engine.tools import TOOLS, Tool

        mock_plan.return_value = planner.Plan("data", "English", [{"tool": "indicator_series", "indicator": "GDP growth"}])
        fake_tool = Tool("indicator_series", "", lambda **_: SERIES, {"indicator": CatalogEntity.INDICATOR})
        patcher = patch.dict(TOOLS, {"indicator_series": fake_tool})
        patcher.start()
        self.addCleanup(patcher.stop)
        instance = ChatInstance.objects.create(title="t")
        events = self.run_pipeline(instance=instance)

        self.assertEqual([e["type"] for e in events][:3], ["status", "status", "status"])
        deltas = "".join(e["text"] for e in events if e["type"] == "delta")
        self.assertTrue(deltas.startswith("<p>GDP grew 7.7% in 2018 EC.</p><h4>GDP Growth: annual</h4>"))
        done = events[-1]
        self.assertEqual(done["type"], "done")
        self.assertNotIn("message", done)
        self.assertTrue(done["verified"])
        self.assertEqual(done["sources"], ["MoPD"])
        self.assertEqual(QuestionHistory.objects.get(id=done["history_id"]).response, deltas)
        trace = AnswerTrace.objects.get()
        self.assertEqual(trace.resolved[0]["match"]["name"], "GDP Growth")

    @patch("ai.engine.pipeline.compose.stream", fake_stream("<p>No match.</p>"))
    @patch("ai.engine.pipeline.catalog.resolve", return_value=[])
    @patch("ai.engine.pipeline.planner.plan")
    def test_unresolved_entity_is_reported_not_guessed(self, mock_plan, _resolve):
        mock_plan.return_value = planner.Plan("data", "English", [{"tool": "indicator_series", "indicator": "zzz"}])
        events = self.run_pipeline()
        self.assertEqual(events[-1]["type"], "done")
        self.assertIn('No indicator matching "zzz"', AnswerTrace.objects.get().tool_calls[0]["error"])

    @patch("ai.engine.pipeline.planner.plan", side_effect=LLMError("down"))
    def test_gateway_failure_ends_with_an_error_event(self, _plan):
        events = self.run_pipeline()
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(AnswerTrace.objects.get().error, "down")


class ChatSocketOwnershipTests(TransactionTestCase):
    async def connect(self, instance_id, user=None):
        from channels.routing import URLRouter
        from channels.testing import WebsocketCommunicator

        from ai.routing import websocket_urlpatterns

        communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/chat/{instance_id}/")
        if user is not None:
            communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected

    def test_owner_and_unauthenticated_clients_can_open_a_chat(self):
        async def scenario():
            User = get_user_model()
            owner = await database_sync_to_async(User.objects.create_user)(username="a", email="a@x.test", password="p")
            instance = await database_sync_to_async(ChatInstance.objects.create)(title="t", user=owner)
            return await self.connect(instance.id, user=owner), await self.connect(instance.id)

        self.assertEqual(async_to_sync(scenario)(), (True, True))

    def test_signed_in_user_cannot_open_someone_elses_chat(self):
        async def scenario():
            User = get_user_model()
            owner = await database_sync_to_async(User.objects.create_user)(username="a", email="a@x.test", password="p")
            other = await database_sync_to_async(User.objects.create_user)(username="b", email="b@x.test", password="p")
            instance = await database_sync_to_async(ChatInstance.objects.create)(title="t", user=owner)
            return await self.connect(instance.id, user=other)

        self.assertFalse(async_to_sync(scenario)())


class AmharicAnswerTests(TestCase):
    @patch("ai.engine.pipeline.planner.plan")
    def test_corrupted_amharic_is_retried_and_never_sent(self, mock_plan):
        from ai.engine.pipeline import answer_stream

        mock_plan.return_value = planner.Plan("general", "Amharic", [])
        drafts = iter(["<p>የጤናစောင့်leት</p>", "<p>የጤና ሥርዓት</p>"])
        temperatures = []

        async def fake_compose(*args, temperature=None, **kwargs):
            temperatures.append(temperature)
            yield next(drafts)

        with patch("ai.engine.pipeline.compose.stream", fake_compose):
            async def collect():
                return [e async for e in answer_stream("ሰላም")]
            events = async_to_sync(collect)()

        self.assertEqual([e["text"] for e in events if e["type"] == "delta"], ["<p>የጤና ሥርዓት</p>"])
        self.assertEqual(temperatures, [0, 0.4])
        self.assertTrue(events[-1]["verified"])


def fake_pipeline(*events):
    async def stream(question, instance=None):
        for event in events:
            yield event
    return stream


ENGLISH = fake_pipeline(
    {"type": "status", "stage": "planning"},
    {"type": "status", "stage": "writing", "language": "English"},
    {"type": "delta", "text": "<p>GDP grew "}, {"type": "delta", "text": "7.7%.</p>"},
    {"type": "done", "history_id": 1, "sources": ["MoPD"], "tools": ["indicator_series"], "verified": True},
)
AMHARIC = fake_pipeline(
    {"type": "status", "stage": "writing", "language": "Amharic"},
    {"type": "delta", "text": "<p>እድገት 7.7 ነው።</p>"}, {"type": "delta", "text": "<h4>t</h4>"},
    {"type": "done", "history_id": 2, "sources": [], "tools": ["organization_score"], "verified": True},
)
FAILED = fake_pipeline({"type": "status", "stage": "planning"}, {"type": "error", "message": "Try again shortly."})


class CompatTests(SimpleTestCase):
    def run_compat(self, stream, native):
        from ai.engine import compat

        sent = []

        async def send(payload):
            sent.append(payload)

        with patch("ai.engine.compat.answer_stream", stream):
            async_to_sync(compat.stream_answer)("q", instance=None, send=send, is_native_client=native,
                                               preview=lambda text: f"preview:{len(text)}")
        return sent

    def test_english_streams_to_the_app_without_a_repeat(self):
        sent = self.run_compat(ENGLISH, native=True)
        self.assertEqual(sent, [
            {"message": "<p>GDP grew ", "preview": "preview:12", "is_stream": True},
            {"message": "7.7%.</p>", "preview": "preview:21", "is_stream": True},
        ])

    def test_browser_also_gets_the_final_message(self):
        sent = self.run_compat(ENGLISH, native=False)
        self.assertEqual(sent[-1], {"message": "<p>GDP grew 7.7%.</p>", "is_stream": False, "is_final": True,
                                    "route": "get_time_series_context"})

    def test_amharic_arrives_as_one_final_message(self):
        sent = self.run_compat(AMHARIC, native=True)
        self.assertEqual(sent, [{"message": "<p>እድገት 7.7 ነው።</p><h4>t</h4>", "is_stream": False, "is_final": True,
                                 "route": "get_ministry_score_context"}])

    def test_errors_are_a_final_message(self):
        self.assertEqual(self.run_compat(FAILED, native=True), [
            {"message": "<p>Try again shortly.</p>", "is_stream": False, "is_final": True, "route": "get_general_context"}])


class ChatEndpointTests(TransactionTestCase):
    """/ws/chat/ and /api/ai-chat/ as the mobile app and web chat use them."""

    def make_chat(self, email="owner@mopd.gov.et"):
        User = get_user_model()
        user = User.objects.create_user(username=email, email=email, password="p")
        return user, ChatInstance.objects.create(title="t", user=user)

    def socket_messages(self, instance_id, headers):
        from channels.routing import URLRouter
        from channels.testing import WebsocketCommunicator

        from ai.routing import websocket_urlpatterns

        async def scenario():
            communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/chat/{instance_id}/", headers=headers)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"message": "What is GDP growth?"})
            received = []
            while not await communicator.receive_nothing(timeout=0.4):
                received.append(await communicator.receive_json_from())
            await communicator.disconnect()
            return received
        return async_to_sync(scenario)()

    def test_the_app_gets_the_stream_once(self):
        _, chat = self.make_chat()
        with patch("ai.engine.compat.answer_stream", ENGLISH):
            messages = self.socket_messages(chat.id, headers=[])
        self.assertEqual([m["message"] for m in messages], ["<p>GDP grew ", "7.7%.</p>"])
        self.assertTrue(all(m["is_stream"] for m in messages))

    def test_the_browser_also_gets_the_final_message(self):
        _, chat = self.make_chat()
        with patch("ai.engine.compat.answer_stream", ENGLISH), \
                patch("ai.engine.compat.followups.suggest", AsyncMock(return_value=[])):
            messages = self.socket_messages(chat.id, headers=[(b"origin", b"http://localhost")])
        self.assertEqual(messages[-1]["message"], "<p>GDP grew 7.7%.</p>")
        self.assertTrue(messages[-1]["is_final"])

    def test_rest_answer_shape(self):
        from rest_framework.test import APIClient

        user, chat = self.make_chat()
        client = APIClient()
        client.force_authenticate(user)
        with patch("ai.engine.compat.answer") as pipeline_answer:
            async def fake_answer(question, instance=None):
                return {"answer": "<p>7.7%</p>", "type": "done", "tools": ["indicator_series"]}
            pipeline_answer.side_effect = fake_answer
            response = client.post(f"/api/ai-chat/answer/{chat.id}/", {"question": "GDP?"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], {"chat_instance_id": chat.id, "question": "GDP?", "answer": "<p>7.7%</p>",
                                                 "route": "get_time_series_context", "token_usage": None})

    def test_async_mode_queues_the_answer_with_the_request_id(self):
        from rest_framework.test import APIClient

        user, chat = self.make_chat()
        client = APIClient()
        client.force_authenticate(user)
        with patch("ai.api.views.generate_answer_task") as task:
            task.delay.return_value.id = "task-1"
            response = client.post(f"/api/ai-chat/answer/{chat.id}/?mode=async", {"question": "GDP?"}, format="json",
                                   HTTP_X_REQUEST_ID="req-9")
        self.assertEqual(response.status_code, 202)
        task.delay.assert_called_once_with(chat.id, "GDP?", "req-9")
        self.assertEqual(response.data["data"]["status_url"], "/api/ai-chat/task-status/task-1/")

    def test_history_is_only_for_the_owner(self):
        from rest_framework.test import APIClient

        owner, chat = self.make_chat()
        QuestionHistory.objects.create(instance=chat, question="q", response="a")
        other, _ = self.make_chat("other@mopd.gov.et")
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/ai-chat/history/{chat.id}/").status_code, 404)
        client.force_authenticate(owner)
        self.assertEqual(len(client.get(f"/api/ai-chat/history/{chat.id}/").data["data"]), 1)

    def test_queued_answer_uses_the_same_payload(self):
        from ai.tasks import generate_answer_task

        _, chat = self.make_chat()
        with patch("ai.engine.compat.answer") as pipeline_answer:
            async def fake_answer(question, instance=None):
                return {"type": "error", "message": "Try again shortly."}
            pipeline_answer.side_effect = fake_answer
            result = generate_answer_task.run(chat.id, "GDP?", "req-1")
        self.assertEqual((result["status"], result["status_code"], result["error"]["message"]),
                         ("FAILURE", 503, "Try again shortly."))


class ChatTitleTests(TestCase):
    def chat(self, title="New Chat", questions=1):
        chat = ChatInstance.objects.create(title=title)
        for i in range(questions):
            QuestionHistory.objects.create(instance=chat, question=f"q{i}", response="a")
        return chat

    def ensure(self, chat, question="What was GDP growth in 2017?", model=None):
        from ai.engine import titles

        reply = AsyncMock(return_value=model or {"title": "GDP growth in 2017."})
        with patch.object(titles.llm, "json_completion", reply):
            return async_to_sync(titles.ensure_title)(chat.id, question), reply

    def test_first_answer_names_the_chat_without_moving_it(self):
        chat = self.chat()
        created = ChatInstance.objects.get(id=chat.id).created_at
        title, _ = self.ensure(chat)
        self.assertEqual(title, "GDP growth in 2017")
        chat.refresh_from_db()
        self.assertEqual((chat.title, chat.created_at), ("GDP growth in 2017", created))

    def test_renamed_or_already_titled_chats_are_left_alone(self):
        for chat in (self.chat(title="My budget notes"), self.chat(questions=2), self.chat(questions=0)):
            title, model = self.ensure(chat)
            self.assertIsNone(title)
            model.assert_not_called()

    def test_untitled_chats_count_as_new(self):
        title, _ = self.ensure(self.chat(title=None))
        self.assertEqual(title, "GDP growth in 2017")

    def test_gateway_failure_or_garbled_title_falls_back_to_the_question(self):
        from ai.engine import titles

        chat = self.chat()
        with patch.object(titles.llm, "json_completion", AsyncMock(side_effect=LLMError("down"))):
            title = async_to_sync(titles.ensure_title)(chat.id, "How did the Ministry of Health perform in the year 2017?")
        self.assertEqual(title, "How did the Ministry of Health…")
        self.assertEqual(titles.fallback("የዋጋ ግሽበት ስንት ነው?"), "የዋጋ ግሽበት ስንት ነው")
        title, _ = self.ensure(self.chat(), question="የዋጋ ግሽበት ስንት ነው?", model={"title": "የዋጋ ግሽ၀ት"})
        self.assertEqual(title, "የዋጋ ግሽበት ስንት ነው")

    def test_browser_is_told_the_new_title_and_the_app_is_not(self):
        from ai.engine import compat

        for native, expected in ((False, True), (True, False)):
            chat = self.chat()
            sent = []

            async def send(payload):
                sent.append(payload)

            with patch("ai.engine.compat.answer_stream", ENGLISH), \
                    patch("ai.engine.compat.titles.suggest", AsyncMock(return_value="GDP growth")), \
                    patch("ai.engine.compat.followups.suggest", AsyncMock(return_value=[])):
                async_to_sync(compat.stream_answer)("q", instance=chat, send=send, is_native_client=native,
                                                   preview=lambda text: "")
            event = {"event": "chat_title", "chat_instance_id": chat.id, "title": "GDP growth"}
            self.assertEqual(event in sent, expected)
            chat.refresh_from_db()
            self.assertEqual(chat.title, "GDP growth")


class ConversationTests(TestCase):
    """The chat's earlier turns reach the planner and the writer."""

    def test_the_last_five_turns_are_kept_and_answers_cut(self):
        history = [{"question": f"q{i}", "response": "<p>" + "x" * 900 + "</p>"} for i in range(7)]
        text = planner.conversation(history, answer_chars=700)
        self.assertNotIn("User: q1\n", text)
        self.assertIn("User: q2\n", text)
        self.assertIn("Assistant: " + "x" * 700 + "\n", text)
        self.assertNotIn("x" * 701, text)
        self.assertEqual(planner.conversation([]), "")

    def test_the_writer_is_given_the_conversation(self):
        from ai.engine import compose

        for kind, results in (("data", [SERIES]), ("general", [])):
            messages = compose.messages_for(kind, "and 2016?", "English", results, conversation="Conversation so far:\nUser: GDP?\n\n")
            self.assertTrue(messages[1]["content"].startswith("Conversation so far:\nUser: GDP?\n\nQuestion: and 2016?"))

    @patch("ai.engine.pipeline.planner.plan")
    def test_a_follow_up_may_quote_earlier_figures(self, mock_plan):
        from ai.engine.pipeline import answer_stream

        instance = ChatInstance.objects.create(title="t")
        QuestionHistory.objects.create(instance=instance, question="Coffee exports?",
                                       response="<p>Coffee earned 2.74 billion USD in 2018 EC.</p>")
        mock_plan.return_value = planner.Plan("general", "English", [])
        seen = {}

        async def fake_compose(*args, conversation="", **kwargs):
            seen["conversation"] = conversation
            yield "<p>In short, coffee brought in 2.74 billion USD.</p>"

        with patch("ai.engine.pipeline.compose.stream", fake_compose):
            async def collect():
                return [e async for e in answer_stream("explain that simply", instance=instance)]
            events = async_to_sync(collect)()

        self.assertIn("User: Coffee exports?\nAssistant: Coffee earned 2.74 billion USD", seen["conversation"])
        self.assertEqual(mock_plan.call_args.args[1][0]["question"], "Coffee exports?")
        self.assertTrue(events[-1]["verified"])


class LanguageTests(SimpleTestCase):
    def test_an_explicit_request_wins_over_the_script(self):
        cases = {
            "make the response in Amharic": "Amharic",
            "What is GDP growth? answer in Amharic": "Amharic",
            "translate that to amharic": "Amharic",
            "Amharic please": "Amharic",
            "amharic": "Amharic",
            "What is the Amharic speaking population?": "English",
            "GDP growth?": "English",
            "የኢትዮጵያ ጥቅል ምርት ዕድገት": "Amharic",
            "ጥቅል ምርት ዕድገት በእንግሊዝኛ": "English",
            "in english please": "English",
        }
        for question, language in cases.items():
            with self.subTest(question):
                self.assertEqual(planner.detect_request_language(question), language)

    def test_a_requested_language_stays_for_the_chat(self):
        asked = [{"question": "GDP?"}, {"question": "answer in Amharic"}]
        self.assertEqual(planner.reply_language("and inflation?", asked), "Amharic")
        self.assertEqual(planner.reply_language("and inflation?", asked + [{"question": "now in English"}]), "English")
        self.assertEqual(planner.reply_language("and inflation?", [{"question": "ሰላም"}]), "English")
        self.assertEqual(planner.reply_language("ዋጋ ግሽበት?", [{"question": "in English please"}]), "Amharic")

    def test_the_writer_is_told_it_can_answer_in_either_language(self):
        from ai.engine import compose

        system = compose.messages_for("general", "answer that in Amharic", "Amharic")[0]["content"]
        self.assertIn("give that answer again in Amharic", system)
        self.assertIn("Never say you can only answer in another language", system)


class FollowUpTests(TestCase):
    def test_suggestions_are_cleaned(self):
        from ai.engine import followups

        raw = ["1. Compare with 2016", "compare with 2016?", "What is GDP growth?", "", "x" * 120,
               "- Show coffee exports by quarter", "Which ministries scored lowest?", "One more"]
        self.assertEqual(followups.clean(raw, "What is GDP growth"), [
            "Compare with 2016", "Show coffee exports by quarter", "Which ministries scored lowest?"])

    def test_gateway_failure_gives_no_suggestions(self):
        from ai.engine import followups

        with patch.object(followups.llm, "json_completion", AsyncMock(side_effect=LLMError("down"))):
            self.assertEqual(async_to_sync(followups.suggest)("q", "<p>a</p>"), [])

    def test_browser_gets_suggestions_and_the_app_does_not(self):
        from ai.engine import compat

        chat = ChatInstance.objects.create(title="GDP")
        for native in (False, True):
            sent = []

            async def send(payload):
                sent.append(payload)

            suggest = AsyncMock(return_value=["Compare with 2016"])
            with patch("ai.engine.compat.answer_stream", ENGLISH), \
                    patch("ai.engine.compat.followups.suggest", suggest):
                async_to_sync(compat.stream_answer)("q", instance=chat, send=send, is_native_client=native,
                                                   preview=lambda text: "")
            event = {"event": "followups", "chat_instance_id": chat.id, "history_id": 1,
                     "questions": ["Compare with 2016"]}
            self.assertEqual(event in sent, not native)
            self.assertEqual(suggest.await_count, 0 if native else 1)
            if not native:
                self.assertEqual(suggest.await_args.args, ("q", "<p>GDP grew 7.7%.</p>"))


class GatewayConfigTests(SimpleTestCase):
    def test_full_endpoint_urls_are_reduced_to_the_v1_base(self):
        from ai.engine.llm import DEFAULT_GATEWAY, _base_url

        self.assertEqual(_base_url("https://llm.mopd.gov.et/v1/chat/completions"), "https://llm.mopd.gov.et/v1")
        self.assertEqual(_base_url("https://llm.mopd.gov.et/v1/embeddings/"), "https://llm.mopd.gov.et/v1")
        self.assertEqual(_base_url("http://localhost:8001"), "http://localhost:8001/v1")
        self.assertEqual(_base_url("not a url"), DEFAULT_GATEWAY)
