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
