from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from AI.infrastructure.translation import detect_request_language
from AI.infrastructure.vectorstore import _extract_query_hints, _metadata_relevance_score
from AI.parsing.entity_aliases import has_goal_reference, has_policy_area_reference, has_time_series_reference
from AI.parsing.query_parser import classify_intent, extract_performance_type, extract_year_quarter
from AI.parsing.rules import match_performance_vocabulary
from AI.mcp_tools import execute_mcp_tool_plan, resolve_mcp_tool_plan
from AI.models import ChatInstance
from AI.application import AnswerResult, format_history_records_for_llm, generate_answer
from AI.application.services import build_retrieval_query


class AIVectorstoreTests(TestCase):
    def test_extract_query_hints_detects_ministry_year_quarter(self):
        hints = _extract_query_hints("MoH score for 2024 Q2")
        self.assertEqual(hints["year"], "2024")
        self.assertEqual(hints["quarter"], "6month")
        self.assertIn("moh", hints["entity_aliases"])

    def test_metadata_relevance_score_prefers_exact_indicator_and_ministry(self):
        hints = _extract_query_hints("Show 1.2.1 for MoH in 2024")
        doc = SimpleNamespace(
            page_content="GDP content",
            metadata={
                "indicator_code": "1.2.1",
                "responsible_ministry_code": "MoH",
                "responsible_ministry_eng": "Ministry of Health",
                "year": "2024",
            },
        )
        self.assertGreaterEqual(_metadata_relevance_score(doc, hints), 20)

    def test_policy_area_reference_can_use_document_metadata_aliases(self):
        doc = SimpleNamespace(metadata={"policy_area_eng": "Agriculture Sector"})
        self.assertTrue(has_policy_area_reference("agriculture performance", docs=[doc]))

    def test_goal_reference_can_use_document_metadata_aliases(self):
        doc = SimpleNamespace(metadata={"goal_name": "Reduce Poverty", "goal_code": "Goal 1"})
        self.assertTrue(has_goal_reference("reduce poverty goal", docs=[doc]))

    def test_time_series_reference_can_use_document_metadata_aliases(self):
        doc = SimpleNamespace(metadata={"indicator_eng": "Gross Domestic Product Growth", "indicator_code": "1.1.1"})
        self.assertTrue(has_time_series_reference("show gross domestic product growth", docs=[doc]))

    def test_detect_request_language_amharic(self):
        self.assertEqual(detect_request_language("የጂዲፒ እድገት ምንድነው"), "Amharic")


class AIMCPRoutingTests(TestCase):
    def test_classify_intent_rule_based_ministry_performance(self):
        intent = classify_intent(None, "Give me weak KPIs for MoH in 2024")
        self.assertEqual(intent, "get_ministry_performance_context")

    def test_classify_intent_rule_based_time_series(self):
        intent = classify_intent(None, "Show Ethiopia GDP trend from 2020 to 2024")
        self.assertEqual(intent, "get_time_series_context")

    def test_extract_year_quarter_rule_based(self):
        extracted = extract_year_quarter(None, "MoH score for 2024 Q2")
        self.assertEqual(extracted["year"], "2024")
        self.assertEqual(extracted["quarter"], "6month")

    def test_extract_performance_type_rule_based(self):
        performance_type = extract_performance_type(None, "Show missing data indicators for MoA")
        self.assertEqual(performance_type, "no_data")

    def test_match_performance_vocabulary_rule_based(self):
        self.assertEqual(match_performance_vocabulary("this ministry is lagging badly"), "weak_performance")

    @patch("AI.tools.planner.classify_intent", return_value="get_general_context")
    def test_resolve_mcp_tool_plan_fallback_preserves_unknown(self, _mock):
        plan = resolve_mcp_tool_plan(llm=None, question="coffee", docs=[object()])
        self.assertEqual(plan.tool_name, "get_general_context")

    @patch("AI.tools.handlers.extract_year_from_question", return_value=2024)
    @patch("AI.tools.handlers.build_timeseries_context_from_docs", return_value="ts")
    def test_execute_mcp_tool_plan_time_series(self, mock_builder, _mock_year):
        plan = resolve_mcp_tool_plan(llm=None, question="gdp 2024", docs=[object()])
        out = execute_mcp_tool_plan(plan, llm=None, question="gdp 2024", docs=[object()])
        self.assertEqual(out, "ts")
        mock_builder.assert_called_once()

    @patch("AI.tools.handlers.extract_year_quarter", return_value={"year": "2018", "quarter": "12month"})
    @patch("AI.tools.handlers.build_ministry_score_context_from_docs", return_value="score")
    def test_execute_mcp_tool_plan_ministry_score(self, mock_builder, _mock_period):
        plan = resolve_mcp_tool_plan(llm=None, question="moh score", docs=[object()])
        out = execute_mcp_tool_plan(plan, llm=object(), question="moh score", docs=[object()])
        self.assertEqual(out, "score")
        mock_builder.assert_called_once()


class AIServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="tester",
            first_name="Test",
            last_name="User",
            password="StrongPass1!",
        )
        self.instance = ChatInstance.objects.create(user=self.user)

    @patch("AI.application.services.get_llm_instance", return_value=object())
    @patch("AI.application.services.get_retriever")
    def test_generate_answer_retrieval_empty(self, mock_get_retriever, _mock_llm):
        mock_get_retriever.return_value.invoke.return_value = []
        result = generate_answer(self.instance, "unknown query")
        self.assertIsInstance(result, AnswerResult)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.message, "RETRIEVAL_EMPTY")
        self.assertEqual(result.error.get("code"), "RETRIEVAL_EMPTY")

    @patch("AI.application.services.get_llm_instance", return_value=None)
    def test_generate_answer_provider_down(self, _mock_llm):
        result = generate_answer(self.instance, "coffee")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.message, "AI_SERVICE_UNAVAILABLE")
        self.assertEqual(result.error.get("code"), "PROVIDER_DOWN")

    @patch(
        "AI.application.services.resolve_mcp_tool_plan",
        return_value=type("Plan", (), {"tool_name": "get_general_context", "arguments": {}})(),
    )
    @patch("AI.application.services.execute_mcp_tool_plan", return_value=object())
    @patch("AI.application.services.invoke_chat_once", side_effect=ValueError("bad output"))
    @patch("AI.application.services.get_llm_instance", return_value=object())
    @patch("AI.application.services.get_retriever")
    def test_generate_answer_llm_failure(self, mock_get_retriever, _mock_llm, _mock_invoke, _mock_context, _mock_plan):
        mock_get_retriever.return_value.invoke.return_value = [type("Doc", (), {"page_content": "x", "metadata": {}})()]
        result = generate_answer(self.instance, "coffee")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.message, "LLM_FAILURE")
        self.assertEqual(result.error.get("code"), "LLM_FAILURE")

    @patch("AI.application.services.invoke_chat_once", side_effect=TimeoutError("timeout"))
    @patch("AI.application.services.execute_mcp_tool_plan", return_value="ctx")
    @patch(
        "AI.application.services.resolve_mcp_tool_plan",
        return_value=type("Plan", (), {"tool_name": "get_time_series_context", "arguments": {}})(),
    )
    @patch("AI.application.services.get_llm_instance", return_value=object())
    @patch("AI.application.services.get_retriever")
    def test_generate_answer_llm_timeout(
        self,
        mock_get_retriever,
        _mock_llm,
        _mock_plan,
        _mock_context,
        _mock_invoke,
    ):
        mock_get_retriever.return_value.invoke.return_value = [type("Doc", (), {"page_content": "x", "metadata": {}})()]
        result = generate_answer(self.instance, "coffee")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.message, "LLM_TIMEOUT")
        self.assertEqual(result.error.get("code"), "LLM_TIMEOUT")

    def test_format_history_records_for_llm(self):
        history = [
            {"question": "q1", "response": "a1"},
            {"question": "q2", "response": "a2"},
        ]
        out = format_history_records_for_llm(history, max_turns=2)
        self.assertEqual(out[0]["role"], "user")
        self.assertEqual(out[1]["role"], "assistant")
        self.assertEqual(len(out), 4)

    def test_build_retrieval_query_keeps_context_for_follow_up(self):
        query = build_retrieval_query(
            "more indicators",
            history_records=[
                {
                    "question": "Give me list of inflation indicators",
                    "response": "<p>Indicator A</p><p>Indicator B</p>",
                }
            ],
        )
        self.assertIn("Previous user request: Give me list of inflation indicators", query)
        self.assertIn("Follow-up request: more indicators", query)


class AIAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="api@example.com",
            username="api_user",
            first_name="API",
            last_name="User",
            password="StrongPass1!",
        )
        self.instance = ChatInstance.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_answer_requires_question(self):
        response = self.client.post(f"/api/ai-chat/answer/{self.instance.id}/", data={}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message"], "QUESTION_REQUIRED")
        self.assertIn("request_id", response.data)

    @patch("AI.endpoints.api.generate_answer")
    def test_answer_success_payload(self, mock_generate):
        mock_generate.return_value = AnswerResult(
            answer="ok",
            route="get_time_series_context",
            status_code=200,
            message="SUCCESS",
            error=None,
            token_usage={"total_tokens": 10},
        )
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "coffee"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "SUCCESS")
        self.assertEqual(response.data["data"]["answer"], "ok")
        self.assertEqual(response.data["data"]["route"], "get_time_series_context")

    @patch("AI.endpoints.api.synthesize_gemini_tts", return_value=(b"RIFFfake", "audio/wav"))
    def test_tts_prefetch_warms_cache(self, _mock_tts):
        response = self.client.post(
            "/api/ai-chat/tts/prefetch/",
            data={"text": "hello", "language": "English"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "SUCCESS")

    @patch("AI.endpoints.api.translate_text_with_gemini", return_value="ሰላም")
    def test_translate_returns_text(self, _mock_translate):
        response = self.client.post(
            "/api/ai-chat/translate/",
            data={"text": "hello", "target_language": "Amharic"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "SUCCESS")
        self.assertEqual(response.data["data"]["translation"], "ሰላም")

    def test_dependency_health_endpoint(self):
        response = self.client.get("/api/ai-chat/health/dependencies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "SUCCESS")
        self.assertIn("dependencies", response.data["data"])


class KnowledgeBaseBuilderTests(TestCase):
    TOPICS = [{
        "title_ENG": "Macro-Economic Aggregates",
        "categories": [
            {
                "name_ENG": "Economic (GDP) Growth",
                "code": "EG",
                "is_deleted": False,
                "indicators": [
                    {
                        "title_ENG": "GDP Growth",
                        "title_AMH": "የአገር ውስጥ ምርት እድገት",
                        "code": "EG-GDPCP-01",
                        "measurement_units": "%",
                        "frequency": "annual",
                        "source": "MoPD",
                        "description": "Real growth of gross domestic product.",
                        "children": [
                            {"title_ENG": "Agriculture growth", "code": "EG-AGR-01", "children": []},
                            {"title_ENG": "Grouping row without code", "code": "", "children": [
                                {"title_ENG": "Industry growth", "code": "EG-IND-01", "children": []},
                            ]},
                        ],
                    },
                    {"title_ENG": "GDP Growth (duplicate listing)", "code": "EG-GDPCP-01", "children": []},
                ],
            },
            {"name_ENG": "Deleted category", "is_deleted": True, "indicators": [{"title_ENG": "Gone", "code": "X-1"}]},
        ],
    }]

    def test_indicator_documents_walk_children_and_skip_uncoded_rows(self):
        from AI.knowledge_base import KB_SOURCE, indicator_documents

        records = dict(indicator_documents(self.TOPICS))
        self.assertEqual(
            sorted(records),
            ["kb-indicator-EG-AGR-01", "kb-indicator-EG-GDPCP-01", "kb-indicator-EG-IND-01"],
        )
        gdp = records["kb-indicator-EG-GDPCP-01"]
        self.assertEqual(gdp.metadata["indicator_code"], "EG-GDPCP-01")
        self.assertEqual(gdp.metadata["indicator_eng"], "GDP Growth")
        self.assertEqual(gdp.metadata["topic_name"], "Macro-Economic Aggregates")
        self.assertEqual(gdp.metadata["kb_source"], KB_SOURCE)
        self.assertIn("የአገር ውስጥ ምርት እድገት", gdp.page_content)
        self.assertEqual(records["kb-indicator-EG-IND-01"].metadata["parent_indicator"], "Grouping row without code")

    def test_organization_documents_carry_ministry_routing_metadata(self):
        from AI.knowledge_base import organization_documents

        orgs = [{"id": 312, "name": "Ministry of Health", "code": "MoH", "is_active": True}]
        cards = {312: {"policy_areas": [{"name": "Healthcare", "goals": [{"name": "Maternal health"}]}]}}
        (record_id, doc), = organization_documents(orgs, cards)
        self.assertEqual(record_id, "kb-ministry-312")
        self.assertEqual(doc.metadata["responsible_ministry_id"], "312")
        self.assertEqual(doc.metadata["responsible_ministry_code"], "MoH")
        self.assertIn("Healthcare", doc.page_content)
        # Goals have their own records; listing them here made ministries match topical questions.
        self.assertNotIn("Maternal health", doc.page_content)

    def test_goal_documents_are_deduplicated_across_policy_areas(self):
        from AI.knowledge_base import goal_documents

        areas = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        shared = {"id": 9, "name": "Shared goal", "code": "GA-9"}
        cards = {1: {"goals": [shared]}, 2: {"goals": [shared, {"id": 10, "name": "Other", "code": "GA-10"}]}}
        self.assertEqual([key for key, _ in goal_documents(areas, cards)], ["kb-goal-9", "kb-goal-10"])


class DPMESMinistryClientTests(TestCase):
    CARD = {
        "name": "Ministry of Health",
        "code": "MoH",
        "score": {"avg_score": 70.62, "color": "#FFBF00"},
        "policy_areas": [{"name": "Healthcare", "score": {"avg_score": 68.39}}],
    }
    RANGES = [
        {"name_en": "On Track", "color": "#6FC327", "kpis": [{"id": 1, "name": "Good KPI", "records": [{"score": 90.0}]}]},
        {"name_en": "Weak Performance", "color": "#FF7259", "kpis": [
            {"id": 2, "name": "Weak KPI", "records": [{"score": 55.0}]},
        ]},
        {"name_en": "Requires Intervention", "color": "#FF0000", "kpis": [
            {"id": 3, "name": "Worst KPI", "records": [{"score": 10.0}]},
        ]},
    ]

    def test_period_treats_default_12month_as_annual(self):
        from AI.infrastructure.clients import _dpmes_period

        with patch("AI.infrastructure.clients.dpmes2.current_ethiopian_year", return_value=2019):
            self.assertEqual(_dpmes_period(None, "12month"), {"year": 2018})
            self.assertEqual(_dpmes_period("2017", "6month"), {"year": 2017, "quarter": 2})

    @patch("AI.infrastructure.clients.dpmes2.organization_scorecard")
    def test_fetch_ministry_score_keeps_formatter_shape(self, mock_card):
        from AI.infrastructure.clients import fetch_ministry_score
        from AI.shared.upstream import format_ministry_score

        mock_card.return_value = self.CARD
        payload = fetch_ministry_score("312", year="2018", quarter="12month")
        self.assertEqual(payload["ministry_score_card"]["score"], 70.62)
        self.assertEqual(payload["ministry_score_card"]["quarter"], "Annual")
        html = format_ministry_score(payload)
        self.assertIn("Ministry of Health", html)
        self.assertIn("Healthcare", html)

    @patch("AI.infrastructure.clients.dpmes2.kpis_by_score_range")
    @patch("AI.infrastructure.clients.dpmes2.organization_scorecard")
    def test_fetch_ministry_performance_lists_weakest_first(self, mock_card, mock_ranges):
        from AI.infrastructure.clients import fetch_ministry_performance

        mock_card.return_value = self.CARD
        mock_ranges.return_value = self.RANGES
        payload = fetch_ministry_performance("312", year="2018", performance_type="weak_performance")
        self.assertEqual([kpi["indicator_name"] for kpi in payload["kpis"]], ["Worst KPI", "Weak KPI"])

    @patch("AI.infrastructure.clients.dpmes2.organization_scorecard")
    def test_fetch_ministry_score_returns_empty_when_dpmes_fails(self, mock_card):
        from AI.infrastructure.clients import fetch_ministry_score
        from dashboard import dpmes2

        mock_card.side_effect = dpmes2.DPMES2Error("down")
        self.assertEqual(fetch_ministry_score("312", year="2018"), {})


class ToolContextDocSelectionTests(TestCase):
    @patch("AI.shared.context.fetch_ministry_score", return_value={})
    def test_ministry_score_context_skips_records_without_ministry(self, mock_fetch):
        from AI.shared.context import build_ministry_score_context_from_docs

        indicator = SimpleNamespace(page_content="Health spending", metadata={"indicator_code": "HEA-09"})
        ministry = SimpleNamespace(page_content="Ministry of Health", metadata={"responsible_ministry_id": "312"})
        build_ministry_score_context_from_docs([indicator, ministry], {"year": "2018"}, max_docs=1)
        mock_fetch.assert_called_once_with("312", year="2018", quarter=None)

    @patch("AI.shared.context.fetch_indicator_time_series", return_value={})
    def test_time_series_context_prefers_records_with_codes(self, mock_fetch):
        from AI.shared.context import build_timeseries_context_from_docs

        ministry = SimpleNamespace(page_content="National Bank", metadata={"responsible_ministry_id": "5"})
        indicator = SimpleNamespace(page_content="GDP Growth", metadata={"indicator_code": "EG-GDPCP-01"})
        build_timeseries_context_from_docs([ministry, indicator], year=None, max_docs=1)
        mock_fetch.assert_called_once_with("EG-GDPCP-01", year=None)
