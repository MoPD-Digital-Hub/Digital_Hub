import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from ai.models import AnswerTrace, CatalogEntity, ChatInstance, QuestionHistory
from ai.engine import catalog, planner, render, verify
from ai.engine.catalog import CatalogIndex, Match
from ai.engine.llm import LLMError


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
            with patch.object(catalog, "fetch_time_series_topics", return_value=[]), \
                    patch.object(catalog, "_indicator_rows", return_value=[dict(r) for r in rows]), \
                    patch.object(catalog.llm, "embed_documents", side_effect=embed) as embedded:
                return catalog.sync(include_dpmes=False, log=lambda *_: None), embedded.call_count

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
        with patch("ai.engine.compat.answer_stream", ENGLISH):
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


class GatewayConfigTests(SimpleTestCase):
    def test_full_endpoint_urls_are_reduced_to_the_v1_base(self):
        from ai.engine.llm import DEFAULT_GATEWAY, _base_url

        self.assertEqual(_base_url("https://llm.mopd.gov.et/v1/chat/completions"), "https://llm.mopd.gov.et/v1")
        self.assertEqual(_base_url("https://llm.mopd.gov.et/v1/embeddings/"), "https://llm.mopd.gov.et/v1")
        self.assertEqual(_base_url("http://localhost:8001"), "http://localhost:8001/v1")
        self.assertEqual(_base_url("not a url"), DEFAULT_GATEWAY)
