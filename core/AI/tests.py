from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from AI.domain import INTENTS
from AI.models import ChatInstance
from AI.selectors import resolve_intent
from AI.services import AnswerResult, format_history_records_for_llm, generate_answer


class AISelectorTests(TestCase):
    @patch("AI.selectors.selectors.classify_intent", return_value=INTENTS["UNKNOWN"])
    def test_resolve_intent_preserves_unknown(self, _mock):
        intent = resolve_intent(llm=None, question="coffee", docs=[object()])
        self.assertEqual(intent, INTENTS["UNKNOWN"])

    @patch("AI.selectors.selectors.extract_year_from_question", return_value=2024)
    @patch("AI.selectors.selectors.build_timeseries_context_from_docs", return_value="ts")
    def test_build_context_time_series(self, mock_builder, _mock_year):
        from AI.selectors import build_context_for_intent

        out = build_context_for_intent(INTENTS["TIME_SERIES"], llm=None, question="gdp 2024", docs=[object()])
        self.assertEqual(out, "ts")
        mock_builder.assert_called_once()

    @patch("AI.selectors.selectors.extract_year_quarter", return_value={"year": "2018", "quarter": "12month"})
    @patch("AI.selectors.selectors.build_ministry_score_context_from_docs", return_value="score")
    def test_build_context_ministry_score(self, mock_builder, _mock_period):
        from AI.selectors import build_context_for_intent

        out = build_context_for_intent(INTENTS["MINISTRY_SCORE"], llm=object(), question="moh score", docs=[object()])
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

    @patch("AI.services.services.get_llm_instance", return_value=object())
    @patch("AI.services.services.get_retriever")
    def test_generate_answer_retrieval_empty(self, mock_get_retriever, _mock_llm):
        mock_get_retriever.return_value.invoke.return_value = []
        result = generate_answer(self.instance, "unknown query")
        self.assertIsInstance(result, AnswerResult)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.message, "RETRIEVAL_EMPTY")
        self.assertEqual(result.error.get("code"), "RETRIEVAL_EMPTY")

    @patch("AI.services.services.get_llm_instance", return_value=None)
    def test_generate_answer_provider_down(self, _mock_llm):
        result = generate_answer(self.instance, "coffee")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.message, "AI_SERVICE_UNAVAILABLE")
        self.assertEqual(result.error.get("code"), "PROVIDER_DOWN")

    @patch("AI.services.services.resolve_intent", return_value=INTENTS["UNKNOWN"])
    @patch("AI.services.services.get_llm_instance", return_value=object())
    @patch("AI.services.services.get_retriever")
    def test_generate_answer_bad_prompt_output(self, mock_get_retriever, _mock_llm, _mock_intent):
        mock_get_retriever.return_value.invoke.return_value = [type("Doc", (), {"page_content": "x", "metadata": {}})()]
        result = generate_answer(self.instance, "coffee")
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.message, "BAD_PROMPT_OUTPUT")
        self.assertEqual(result.error.get("code"), "BAD_PROMPT_OUTPUT")

    @patch("AI.services.services.invoke_chat_once", side_effect=TimeoutError("timeout"))
    @patch("AI.services.services.build_context_for_intent", return_value="ctx")
    @patch("AI.services.services.resolve_intent", return_value=INTENTS["TIME_SERIES"])
    @patch("AI.services.services.get_llm_instance", return_value=object())
    @patch("AI.services.services.get_retriever")
    def test_generate_answer_llm_timeout(
        self,
        mock_get_retriever,
        _mock_llm,
        _mock_intent,
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

    @patch("AI.api.api.generate_answer")
    def test_answer_success_payload(self, mock_generate):
        mock_generate.return_value = AnswerResult(
            answer="ok",
            intent=INTENTS["TIME_SERIES"],
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

    def test_dependency_health_endpoint(self):
        response = self.client.get("/api/ai-chat/health/dependencies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "SUCCESS")
        self.assertIn("dependencies", response.data["data"])
