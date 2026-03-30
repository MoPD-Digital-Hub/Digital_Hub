from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from AI.gemini.client import GeminiClientError
from AI.gemini.config import GeminiSettings, validate_gemini_settings
from AI.gemini.language import detect_language
from AI.gemini.prompting import GeminiPromptBuilder
from AI.gemini.service import ChatGenerationResult, GeminiChatService
from AI.models import ChatInstance, QuestionHistory
from AI.query_preprocessing import QueryPreprocessor
from AI.orchestration.classifier import IntentClassifier
from AI.orchestration.dashboard import DashboardGenerationService, DashboardServiceError
from AI.orchestration.formatter import dashboard_success_message
from AI.orchestration.result import OrchestrationResult
from AI.orchestration.service import AIOrchestrator, OrchestrationError
from AI.orchestration.time_series import TimeSeriesQueryError
from AI.retrieval.config import RetrievalSettings, validate_retrieval_settings
from AI.retrieval.ministry_score import format_public_body_score_context, parse_requested_period
from AI.retrieval.query_normalizer import normalize_retrieval_query
from AI.retrieval.resolver import resolve_indicator_query
from AI.retrieval.service import MilvusContextRetriever, RetrievalError, RetrievalResult
from AI.retrieval.time_series import build_time_series_chart, format_time_series_context


class GeminiLanguageTests(TestCase):
    def test_detect_language_amharic(self):
        self.assertEqual(detect_language("የጂዲፒ እድገት ምንድነው"), "Amharic")

    def test_detect_language_english(self):
        self.assertEqual(detect_language("What is inflation?"), "English")

    def test_detect_language_mixed_prefers_dominant_script(self):
        self.assertEqual(detect_language("GDP በኢትዮጵያ ምን ይመስላል"), "Amharic")


class GeminiPromptTests(TestCase):
    def test_prompt_builder_enforces_same_language(self):
        builder = GeminiPromptBuilder()
        messages, language = builder.build_messages(question="What is inflation?", history_records=[])
        self.assertEqual(language, "English")
        self.assertIn("Response language: English", messages[0]["content"])

    def test_prompt_builder_enforces_amharic(self):
        builder = GeminiPromptBuilder()
        messages, language = builder.build_messages(question="የዋጋ ግሽበት ምንድነው?", history_records=[])
        self.assertEqual(language, "Amharic")
        self.assertIn("Response language: Amharic", messages[0]["content"])


class IntentClassifierTests(TestCase):
    def test_classifies_dashboard_generation(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("generate dashboard about agriculture"), "dashboard_generation")

    def test_dashboard_generation_overrides_time_series_keywords(self):
        classifier = IntentClassifier()
        analyzed = classifier.analyze("generate a dashboard about coffee export trend")
        self.assertEqual(analyzed["primary_intent"], "dashboard_generation")
        self.assertEqual(analyzed["secondary_intents"], ["time_series_query"])

    def test_classifies_create_dashboard_for_agriculture(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("create a dashboard for agriculture performance"), "dashboard_generation")

    def test_classifies_build_export_dashboard(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("build export dashboard"), "dashboard_generation")

    def test_classifies_generate_dashboard_about_gold_export(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("generate dashboard about gold export"), "dashboard_generation")

    def test_classifies_misspelled_dashboard_prompt(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("genrate dashabord about inlation"), "dashboard_generation")

    def test_classifies_multi_entity_dashboard_prompt(self):
        classifier = IntentClassifier()
        analyzed = classifier.analyze("build dashboard about coffee export, gold export and other export")
        self.assertEqual(analyzed["primary_intent"], "dashboard_generation")
        self.assertEqual(analyzed["secondary_intents"], ["time_series_query"])

    def test_classifies_visual_analytics_requests_as_dashboard_generation(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("show me visual data for productive sector"), "dashboard_generation")
        self.assertEqual(classifier.classify("visualize productive sector"), "dashboard_generation")
        self.assertEqual(classifier.classify("I want charts for productive sector"), "dashboard_generation")

    def test_classifies_time_series_query(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("show annual trend for EXP-02.32"), "time_series_query")

    def test_classifies_export_value_question_as_time_series(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("what is the export value of coffee?"), "time_series_query")

    def test_classifies_public_body_performance_queries_as_scorecard(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("MoPD performance"), "scorecard_query")
        self.assertEqual(classifier.classify("public body performance"), "scorecard_query")
        self.assertEqual(classifier.classify("Ministry of Planning and Development performance"), "scorecard_query")

    def test_ministry_reference_without_performance_stays_general(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("Ministry of Health"), "general_query")

    def test_classifies_general_query(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.classify("explain the purpose of DPMES"), "general_query")
        self.assertEqual(classifier.classify("explain ADMAS AI"), "general_query")


class GeminiConfigTests(TestCase):
    def test_validate_settings_accepts_valid_values(self):
        with patch("AI.gemini.config.get_gemini_settings") as mock_settings:
            mock_settings.return_value = GeminiSettings(
                api_key="key",
                model="gemini-2.5-flash",
                timeout_seconds=30,
                temperature=0.2,
                top_p=0.9,
                max_output_tokens=1024,
                max_history_questions=4,
                stream_chunk_chars=180,
            )
            validate_gemini_settings(debug=False)

    def test_validate_settings_requires_key_in_production(self):
        with patch("AI.gemini.config.get_gemini_settings") as mock_settings:
            mock_settings.return_value = GeminiSettings(
                api_key="",
                model="gemini-2.5-flash",
                timeout_seconds=30,
                temperature=0.2,
                top_p=0.9,
                max_output_tokens=1024,
                max_history_questions=4,
                stream_chunk_chars=180,
            )
            with self.assertRaises(ValueError):
                validate_gemini_settings(debug=False)

    def test_validate_retrieval_settings_requires_dependencies(self):
        with patch("AI.retrieval.config.get_retrieval_settings") as mock_settings:
            mock_settings.return_value = RetrievalSettings(
                milvus_uri="",
                collection_name="admas_data",
                embedding_api_base="",
                embedding_model="BAAI/bge-base-en-v1.5",
                embedding_api_key="empty",
                time_series_api_base="",
                time_series_indicator_limit=1,
                retrieval_k=5,
                retrieval_fetch_k=12,
                retrieval_timeout_seconds=30,
            )
            with self.assertRaises(ValueError):
                validate_retrieval_settings(debug=False)


class GeminiServiceTests(TestCase):
    def test_service_returns_result_and_language(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>Hello</p>", "usage": {"total_tokens": 10}},
                "iter_chunks": lambda self, text: iter(["<p>Hello</p>"]),
            },
        )()
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\ntext: inflation context",
                    sources=[{"indicator": "Inflation"}],
                    charts=[{"type": "line", "label": "Inflation", "labels": ["2023", "2024"], "data": [14.2, 19.8]}],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, retriever=fake_retriever)
        result = service.generate(question="Hello", history_records=[])
        self.assertIsInstance(result, ChatGenerationResult)
        self.assertEqual(result.language, "English")
        self.assertEqual(result.answer, "<p>Hello</p>")
        self.assertTrue(result.context_found)
        self.assertEqual(result.sources[0]["indicator"], "Inflation")
        self.assertEqual(result.charts, [])

    def test_service_trims_history(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>Hello</p>", "usage": {}},
                "iter_chunks": lambda self, text: iter([text]),
            },
        )()
        settings = GeminiSettings(
            api_key="key",
            model="gemini-2.5-flash",
            timeout_seconds=30,
            temperature=0.2,
            top_p=0.9,
            max_output_tokens=1024,
            max_history_questions=1,
            stream_chunk_chars=180,
        )
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\ntext: GDP context",
                    sources=[],
                    charts=[],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, settings=settings, retriever=fake_retriever)
        result = service.generate(
            question="Follow up?",
            history_records=[
                {"question": "q1", "response": "a1"},
                {"question": "q2", "response": "a2"},
            ],
        )
        self.assertEqual(result.answer, "<p>Hello</p>")

    def test_trim_history_keeps_last_four_question_response_pairs(self):
        service = GeminiChatService(
            client=type("Client", (), {})(),
            settings=GeminiSettings(
                api_key="key",
                model="gemini-2.5-flash",
                timeout_seconds=30,
                temperature=0.2,
                top_p=0.9,
                max_output_tokens=1024,
                max_history_questions=4,
                stream_chunk_chars=180,
            ),
            retriever=type("Retriever", (), {"retrieve": lambda self, question: RetrievalResult(context="", sources=[], charts=[], query_text=question)})(),
        )
        trimmed = service._trim_history(
            [
                {"question": "q1", "response": "a1"},
                {"question": "q2", "response": "a2"},
                {"question": "q3", "response": "a3"},
                {"question": "q4", "response": "a4"},
                {"question": "q5", "response": "a5"},
                {"question": "q6", "response": "a6"},
            ]
        )
        self.assertEqual([row["question"] for row in trimmed], ["q3", "q4", "q5", "q6"])
        self.assertEqual([row["response"] for row in trimmed], ["a3", "a4", "a5", "a6"])

    def test_service_includes_chart_when_series_is_long_enough(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>Trend answer</p>", "usage": {}},
                "iter_chunks": lambda self, text: iter([text]),
            },
        )()
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\ntext: export trend context",
                    sources=[],
                    charts=[{"type": "line", "label": "Coffee Export", "labels": ["2014", "2015", "2016", "2017"], "data": [1.44, 1.34, 1.43, 2.67]}],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, retriever=fake_retriever)

        chart_result = service.generate(question="What is coffee export?", history_records=[])

        self.assertEqual(chart_result.charts[0]["label"], "Coffee Export")

    def test_service_skips_chart_when_series_is_too_short(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>Short series answer</p>", "usage": {}},
                "iter_chunks": lambda self, text: iter([text]),
            },
        )()
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\ntext: short export context",
                    sources=[],
                    charts=[{"type": "line", "label": "Coffee Export", "labels": ["2016", "2017"], "data": [1.43, 2.67]}],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, retriever=fake_retriever)

        result = service.generate(question="What is coffee export?", history_records=[])
        self.assertEqual(result.charts, [])

    def test_service_respects_explicit_no_chart_request(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>Summary answer</p>", "usage": {}},
                "iter_chunks": lambda self, text: iter([text]),
            },
        )()
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\ntext: export trend context",
                    sources=[],
                    charts=[{"type": "line", "label": "Coffee Export", "labels": ["2014", "2015", "2016", "2017"], "data": [1.44, 1.34, 1.43, 2.67]}],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, retriever=fake_retriever)

        result = service.generate(question="Give me only the summary text and do not generate the chart", history_records=[])
        self.assertEqual(result.charts, [])

    def test_service_hides_chart_for_public_body_scorecard_questions(self):
        fake_client = type(
            "Client",
            (),
            {
                "generate": lambda self, messages: {"text": "<p>MoPD scored strongly overall.</p>", "usage": {}},
                "iter_chunks": lambda self, text: iter([text]),
            },
        )()
        fake_retriever = type(
            "Retriever",
            (),
            {
                "retrieve": lambda self, question: RetrievalResult(
                    context="Source 1\npublic_body_score_api:\nministry_score: 91.63%",
                    sources=[
                        {
                            "ministry": "Ministry of Planning and Development",
                            "public_body_score": {
                                "responsible_ministry_eng": "Ministry of Planning and Development",
                                "ministry_score_card": {"score": "91.63%", "score_color": "#6FC327"},
                                "policy_areas": [],
                            },
                        }
                    ],
                    charts=[{"type": "line", "label": "Indicator trend", "labels": ["2020", "2021", "2022", "2023"], "data": [10, 20, 30, 40]}],
                    query_text=question,
                )
            },
        )()
        service = GeminiChatService(client=fake_client, retriever=fake_retriever)

        result = service.generate(question="show the ministry scorecard for MoPD", history_records=[])
        self.assertEqual(result.charts, [])


class OrchestrationTests(TestCase):
    @patch("AI.orchestration.dashboard.requests.post")
    def test_dashboard_service_returns_normalized_result(self, mock_post):
        mock_post.return_value = type(
            "Response",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {
                    "id": 25,
                    "prompt": "generate dashboard about agriculture",
                    "share_url": "https://analytics.mopd.gov.et/share/agriculture-dashboard-25/",
                    "title": "Agriculture Dashboard",
                },
            },
        )()
        service = DashboardGenerationService()
        result = service.create_dashboard("generate dashboard about agriculture")
        self.assertEqual(result["id"], 25)
        self.assertEqual(result["title"], "Agriculture Dashboard")

    def test_dashboard_success_message_amharic(self):
        message = dashboard_success_message("Agriculture Dashboard", "https://example.com", "Amharic")
        self.assertIn("ዳሽቦርድዎ ተዘጋጅቷል", message)

    def test_orchestrator_routes_dashboard_generation(self):
        orchestrator = AIOrchestrator(
            classifier=type(
                "Classifier",
                (),
                {"analyze": lambda self, question: {"primary_intent": "dashboard_generation", "secondary_intents": ["time_series_query"]}},
            )(),
            dashboard_service=type(
                "DashboardService",
                (),
                {
                    "create_dashboard": lambda self, prompt: {
                        "id": 25,
                        "prompt": prompt,
                        "share_url": "https://analytics.mopd.gov.et/share/agriculture-dashboard-25/",
                        "title": "Agriculture Dashboard",
                    }
                },
            )(),
        )
        result = orchestrator.handle(question="generate dashboard about agriculture", history_records=[])
        self.assertEqual(result.intent, "dashboard_generation")
        self.assertEqual(result.response_type, "dashboard_link")
        self.assertEqual(result.secondary_intents, ["time_series_query"])
        self.assertIn("share/agriculture-dashboard-25", result.message)

    def test_orchestrator_corrects_dashboard_prompt_before_tool_call(self):
        captured = {}
        orchestrator = AIOrchestrator(
            dashboard_service=type(
                "DashboardService",
                (),
                {
                    "create_dashboard": lambda self, prompt: captured.setdefault(
                        "result",
                        {
                            "id": 25,
                            "prompt": prompt,
                            "share_url": "https://analytics.mopd.gov.et/share/inflation-dashboard-25/",
                            "title": "Inflation Dashboard",
                        },
                    )
                },
            )(),
        )
        result = orchestrator.handle(question="genrate dashabord about inlation", history_records=[])
        self.assertEqual(result.tool_state["resolved_prompt"], "generate dashboard about inflation")
        self.assertIn("inflation-dashboard-25", result.message)

    def test_dashboard_follow_up_generate_it_uses_previous_topic(self):
        captured = {}
        orchestrator = AIOrchestrator(
            dashboard_service=type(
                "DashboardService",
                (),
                {
                    "create_dashboard": lambda self, prompt: captured.setdefault(
                        "result",
                        {
                            "id": 25,
                            "prompt": prompt,
                            "share_url": "https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/",
                            "title": "Coffee Export Dashboard",
                        },
                    )
                },
            )(),
        )
        history = [
            {
                "question": "generate a dashboard about coffee export",
                "response": "<p>Some mistaken text answer</p>",
                "tool_data": {},
            }
        ]
        result = orchestrator.handle(question="generate it", history_records=history)
        self.assertEqual(result.intent, "dashboard_generation")
        self.assertEqual(result.tool_state["resolved_prompt"], "generate a dashboard about coffee export")
        self.assertIn("coffee-export-dashboard-25", result.message)

    def test_dashboard_follow_up_show_link_returns_existing_link(self):
        orchestrator = AIOrchestrator()
        history = [
            {
                "question": "generate a dashboard about coffee export",
                "response": "<p>Your dashboard is ready</p>",
                "tool_data": {
                    "intent": "dashboard_generation",
                    "topic": "coffee export",
                    "resolved_prompt": "generate a dashboard about coffee export",
                    "last_tool_result": {
                        "id": 25,
                        "prompt": "generate a dashboard about coffee export",
                        "share_url": "https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/",
                        "title": "Coffee Export Dashboard",
                    },
                },
            }
        ]
        result = orchestrator.handle(question="show me the link", history_records=history)
        self.assertEqual(result.intent, "dashboard_generation")
        self.assertIn("coffee-export-dashboard-25", result.message)

    def test_dashboard_follow_up_build_dashboard_about_that_uses_previous_topic(self):
        captured = {}
        orchestrator = AIOrchestrator(
            dashboard_service=type(
                "DashboardService",
                (),
                {
                    "create_dashboard": lambda self, prompt: captured.setdefault(
                        "result",
                        {
                            "id": 31,
                            "prompt": prompt,
                            "share_url": "https://analytics.mopd.gov.et/share/gold-export-dashboard-31/",
                            "title": "Gold Export Dashboard",
                        },
                    )
                },
            )(),
        )
        history = [
            {
                "question": "gold export",
                "response": "<p>Gold export data summary</p>",
                "tool_data": {},
            }
        ]
        result = orchestrator.handle(question="build dashboard about that", history_records=history)
        self.assertEqual(result.intent, "dashboard_generation")
        self.assertEqual(result.tool_state["resolved_prompt"], "generate a dashboard about gold export")
        self.assertIn("gold-export-dashboard-31", result.message)

    def test_orchestrator_passes_multi_entity_dashboard_prompt_through(self):
        captured = {}
        orchestrator = AIOrchestrator(
            dashboard_service=type(
                "DashboardService",
                (),
                {
                    "create_dashboard": lambda self, prompt: captured.setdefault(
                        "result",
                        {
                            "id": 44,
                            "prompt": prompt,
                            "share_url": "https://analytics.mopd.gov.et/share/export-dashboard-44/",
                            "title": "Export Dashboard",
                        },
                    )
                },
            )(),
        )
        prompt = "build dashboard about coffee export, gold export and other export"
        result = orchestrator.handle(question=prompt, history_records=[])
        self.assertEqual(result.intent, "dashboard_generation")
        self.assertEqual(result.tool_state["resolved_prompt"], prompt)

    def test_orchestrator_routes_time_series_queries(self):
        orchestrator = AIOrchestrator(
            classifier=type(
                "Classifier",
                (),
                {"analyze": lambda self, question: {"primary_intent": "time_series_query", "secondary_intents": []}},
            )(),
            time_series_service=type(
                "TimeSeriesService",
                (),
                {
                    "answer": lambda self, question, history_records: ChatGenerationResult(
                        answer="<p>Time-series answer</p>",
                        language="English",
                        usage={"total_tokens": 10},
                        sources=[],
                        charts=[{"type": "line", "label": "Coffee Export", "labels": ["2014", "2015", "2016", "2017"], "data": [1.44, 1.34, 1.43, 2.67]}],
                        context_found=True,
                    )
                },
            )(),
            text_service=type("TextService", (), {})(),
        )
        result = orchestrator.handle(question="show export trend", history_records=[])
        self.assertEqual(result.intent, "time_series_query")
        self.assertEqual(result.charts[0]["label"], "Coffee Export")
        self.assertEqual(result.data["response_type"], "time_series")
        self.assertIn("title", result.data)
        self.assertIn("summary", result.data)
        self.assertIn("data", result.data)

    def test_orchestrator_uses_table_response_for_table_request(self):
        orchestrator = AIOrchestrator(
            classifier=type(
                "Classifier",
                (),
                {"analyze": lambda self, question: {"primary_intent": "time_series_query", "secondary_intents": []}},
            )(),
            time_series_service=type(
                "TimeSeriesService",
                (),
                {
                    "answer": lambda self, question, history_records, preprocessed=None: ChatGenerationResult(
                        answer="<p>Table answer</p>",
                        language="English",
                        usage={"total_tokens": 10},
                        sources=[],
                        charts=[{"type": "line", "label": "Coffee Export", "labels": ["2016", "2017"], "data": [1.43, 2.67]}],
                        context_found=True,
                    )
                },
            )(),
            text_service=type("TextService", (), {})(),
        )
        result = orchestrator.handle(question="show coffee export in table format", history_records=[])
        self.assertEqual(result.response_type, "table")
        self.assertEqual(result.data["data"]["table"]["columns"], ["Period", "Value"])
        self.assertEqual(result.data["data"]["table"]["rows"][0], ["2016", 1.43])

    def test_orchestrator_downgrades_invalid_scorecard_payload_to_text(self):
        orchestrator = AIOrchestrator()
        payload = orchestrator._validate_response_payload(
            {
                "response_type": "scorecard",
                "title": "Invalid scorecard",
                "summary": "<p>No score fields</p>",
                "data": {"primary_domain": "DPMES"},
            },
            question="MoPD performance",
            answer="<p>No score fields</p>",
            sources=[],
        )
        self.assertEqual(payload["response_type"], "text")
        self.assertEqual(payload["data"]["text"], "<p>No score fields</p>")

    def test_orchestrator_returns_not_found_for_missing_scorecard(self):
        orchestrator = AIOrchestrator(
            classifier=type(
                "Classifier",
                (),
                {"analyze": lambda self, question: {"primary_intent": "scorecard_query", "secondary_intents": []}},
            )(),
            scorecard_service=type(
                "ScorecardService",
                (),
                {
                    "answer": lambda self, question, history_records, language, preprocessed=None: type(
                        "ScorecardResult",
                        (),
                        {
                            "answer": "<p>No DPMES performance scorecard data found for this public body.</p>",
                            "language": "English",
                            "scorecard": None,
                            "sources": [],
                            "context_found": False,
                            "found": False,
                        },
                    )()
                },
            )(),
        )
        result = orchestrator.handle(question="MoPD performance", history_records=[])
        self.assertEqual(result.intent, "scorecard_query")
        self.assertEqual(result.response_type, "not_found")
        self.assertEqual(result.charts, [])
        self.assertEqual(result.data["data"]["primary_domain"], "DPMES")

    def test_follow_up_analysis_reconstructs_previous_time_series_topic(self):
        captured = {}
        def answer(self, question, history_records, preprocessed=None):
            captured["question"] = question
            return ChatGenerationResult(
                answer="<p>Detailed GDP analysis</p>",
                language="English",
                usage={"total_tokens": 12},
                sources=[],
                charts=[],
                context_found=True,
            )
        orchestrator = AIOrchestrator(
            time_series_service=type(
                "TimeSeriesService",
                (),
                {"answer": answer},
            )(),
            text_service=type("TextService", (), {})(),
        )
        history = [
            {
                "question": "Ethiopian GDP growth",
                "response": "<p>GDP growth data response</p>",
                "tool_data": {"intent": "time_series_query", "topic": "Ethiopian GDP growth"},
                "chart_data": [],
            }
        ]
        result = orchestrator.handle(question="give me detail analysis", history_records=history)
        self.assertEqual(result.intent, "time_series_query")
        self.assertEqual(captured["question"], "Give me detailed analysis of Ethiopian GDP growth")

    def test_follow_up_explain_more_reuses_previous_context_when_time_series_missing(self):
        captured = {}
        def generate(self, question, history_records, context=None):
            captured["payload"] = {"question": question, "context": context}
            return ChatGenerationResult(
                answer="<p>Expanded explanation</p>",
                language="English",
                usage={"total_tokens": 9},
                sources=[],
                charts=[],
                context_found=True,
            )
        orchestrator = AIOrchestrator(
            time_series_service=type(
                "TimeSeriesService",
                (),
                {
                    "answer": lambda self, question, history_records, preprocessed=None: (_ for _ in ()).throw(TimeSeriesQueryError("No structured time-series data was found."))
                },
            )(),
            text_service=type(
                "TextService",
                (),
                {"generate": generate},
            )(),
        )
        history = [
            {
                "question": "coffee export",
                "response": "<p>Coffee export rose to 2.67 billion USD in 2017.</p>",
                "tool_data": {"intent": "time_series_query", "topic": "coffee export"},
                "chart_data": [{"type": "line", "label": "Coffee Export", "labels": ["2016", "2017"], "data": [1.43, 2.67]}],
            }
        ]
        with self.assertRaises(OrchestrationError) as exc:
            orchestrator.handle(question="explain more", history_records=history)
        self.assertEqual(exc.exception.code, "TIME_SERIES_FAILED")

    def test_follow_up_dashboard_explanation_uses_dashboard_context(self):
        captured = {}
        def generate(self, question, history_records, context=None):
            captured["payload"] = {"question": question, "context": context}
            return ChatGenerationResult(
                answer="<p>Dashboard explanation</p>",
                language="English",
                usage={"total_tokens": 7},
                sources=[],
                charts=[],
                context_found=True,
            )
        orchestrator = AIOrchestrator(
            text_service=type(
                "TextService",
                (),
                {"generate": generate},
            )(),
        )
        history = [
            {
                "question": "generate dashboard about coffee export",
                "response": '<p>Your dashboard is ready: <a href="https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/">link</a></p>',
                "tool_data": {
                    "intent": "dashboard_generation",
                    "topic": "coffee export",
                    "resolved_prompt": "generate dashboard about coffee export",
                    "last_tool_result": {
                        "title": "Coffee Export Dashboard",
                        "share_url": "https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/",
                    },
                },
                "chart_data": [],
            }
        ]
        result = orchestrator.handle(question="explain it", history_records=history)
        self.assertEqual(result.intent, "general_query")
        self.assertEqual(captured["payload"]["question"], "Explain the dashboard about coffee export in more detail.")
        self.assertIn("Dashboard title: Coffee Export Dashboard", captured["payload"]["context"])

    def test_follow_up_detail_info_reuses_previous_topic(self):
        captured = {}
        def generate(self, question, history_records, context=None):
            captured["payload"] = {"question": question, "context": context}
            return ChatGenerationResult(
                answer="<p>Detailed coffee export information</p>",
                language="English",
                usage={"total_tokens": 11},
                sources=[],
                charts=[],
                context_found=True,
            )
        orchestrator = AIOrchestrator(
            time_series_service=type(
                "TimeSeriesService",
                (),
                {
                    "answer": lambda self, question, history_records, preprocessed=None: (_ for _ in ()).throw(TimeSeriesQueryError("No structured time-series data was found."))
                },
            )(),
            text_service=type("TextService", (), {"generate": generate})(),
        )
        history = [
            {
                "question": "coffee export",
                "response": "<p>Coffee export earnings increased.</p>",
                "tool_data": {"intent": "time_series_query", "topic": "coffee export"},
                "chart_data": [],
            }
        ]
        with self.assertRaises(OrchestrationError) as exc:
            orchestrator.handle(question="give me detail info", history_records=history)
        self.assertEqual(exc.exception.code, "TIME_SERIES_FAILED")

    def test_follow_up_table_format_reuses_previous_topic(self):
        captured = {}
        def answer(self, question, history_records, preprocessed=None):
            captured["question"] = question
            return ChatGenerationResult(
                answer="<p>Table-formatted export data</p>",
                language="English",
                usage={"total_tokens": 8},
                sources=[],
                charts=[],
                context_found=True,
            )
        orchestrator = AIOrchestrator(
            time_series_service=type("TimeSeriesService", (), {"answer": answer})(),
            text_service=type("TextService", (), {})(),
        )
        history = [
            {
                "question": "coffee export",
                "response": "<p>Coffee export earnings increased.</p>",
                "tool_data": {"intent": "time_series_query", "topic": "coffee export"},
                "chart_data": [],
            }
        ]
        result = orchestrator.handle(question="okay give me the data in tabl format", history_records=history)
        self.assertEqual(result.intent, "time_series_query")
        self.assertEqual(captured["question"], "Show the data for coffee export in table format")


class TimeSeriesEnrichmentTests(TestCase):
    def test_format_time_series_context_outputs_sections(self):
        formatted = format_time_series_context(
            {
                "indicator": "EXP-02.32",
                "time_series": {
                    "annual": [{"year": "2017", "value": 2.67}],
                    "quarter": [{"year": "2018", "quarter": "Q2", "value": 1.35}],
                    "month": [{"year": "2018", "month": "ጥቅምት", "value": 196.66}],
                },
            }
        )
        self.assertIn("indicator: EXP-02.32", formatted)
        self.assertIn("annual_values", formatted)
        self.assertIn("quarter_values", formatted)
        self.assertIn("month_values", formatted)

    def test_build_time_series_chart_outputs_line_chart(self):
        chart = build_time_series_chart(
            {
                "indicator": "EXP-02.32",
                "time_series": {
                    "annual": [
                        {"year": "2016", "value": 1.43},
                        {"year": "2017", "value": 2.67},
                    ],
                    "quarter": [],
                    "month": [],
                },
            },
            {"indicator_eng": "Coffee Export", "unit_eng": "Billion USD", "indicator_code": "EXP-02.32"},
        )
        self.assertEqual(chart["type"], "line")
        self.assertEqual(chart["label"], "Coffee Export (Billion USD)")
        self.assertEqual(chart["labels"], ["2016", "2017"])
        self.assertEqual(chart["data"], [1.43, 2.67])

    def test_format_public_body_score_context_outputs_sections(self):
        formatted = format_public_body_score_context(
            {
                "id": 25,
                "responsible_ministry_eng": "Ministry of Planning and Development",
                "code": "MoPD",
                "number_of_indicators": 150,
                "ministry_score_card": {
                    "score": "91.63%",
                    "score_color": "#6FC327",
                    "year": 2018,
                    "quarter": "6month",
                },
                "policy_areas": [
                    {
                        "policy_area_eng": "ENSURING SUSTAINABLE MACROECONOMIC MANAGEMENT AND ECONOMIC GROWTH",
                        "score": "86.48%",
                    }
                ],
            }
        )
        self.assertIn("public_body: Ministry of Planning and Development", formatted)
        self.assertIn("ministry_score: 91.63%", formatted)
        self.assertIn("score_year: 2018", formatted)
        self.assertIn("policy_area_scores", formatted)


class QueryPreprocessingTests(TestCase):
    def test_corrects_lightweight_english_typos(self):
        preprocessor = QueryPreprocessor()
        result = preprocessor.preprocess("inlation rate in ethiopia")
        self.assertEqual(result.corrected, "inflation rate in ethiopia")
        self.assertEqual(result.best_query, "inflation rate in ethiopia")

    def test_builds_semantic_variants_for_inflation(self):
        preprocessor = QueryPreprocessor()
        result = preprocessor.preprocess("inlation rate in ethiopia")
        self.assertIn("consumer price inflation rate in ethiopia", result.variants)

    def test_preserves_amharic_input_without_english_correction(self):
        preprocessor = QueryPreprocessor()
        result = preprocessor.preprocess("የዋጋ ግሽበት በኢትዮጵያ")
        self.assertEqual(result.corrected, "የዋጋ ግሽበት በኢትዮጵያ")
        self.assertEqual(result.variants, ["የዋጋ ግሽበት በኢትዮጵያ"])

    def test_parse_requested_period_extracts_year_and_quarter(self):
        year, quarter = parse_requested_period("show Ministry of Planning and Development score for 2018 q3")
        self.assertEqual(year, 2018)
        self.assertEqual(quarter, "9month")

    @patch("AI.retrieval.service.fetch_indicator_time_series")
    def test_retriever_adds_time_series_context_for_indicator_code(self, mock_fetch):
        mock_fetch.return_value = {
            "indicator": "EXP-02.32",
            "time_series": {
                "annual": [{"year": "2017", "value": 2.67}],
                "quarter": [],
                "month": [],
            },
        }
        retriever = MilvusContextRetriever(
            settings=RetrievalSettings(
                milvus_uri="http://localhost:19530",
                collection_name="admas_data",
                embedding_api_base="http://localhost:4001/v1/embeddings",
                embedding_model="BAAI/bge-base-en-v1.5",
                embedding_api_key="empty",
                time_series_api_base="https://time-series.mopd.gov.et/api/mobile",
                time_series_indicator_limit=1,
                retrieval_k=5,
                retrieval_fetch_k=12,
                retrieval_timeout_seconds=30,
            )
        )
        doc = type(
            "Doc",
            (),
            {
                "page_content": "Export indicator description",
                "metadata": {"indicator_code": "EXP-02.32", "indicator_eng": "Export value"},
            },
        )()
        context, charts = retriever._format_context([doc])
        self.assertIn("time_series_api:", context)
        self.assertEqual(charts[0]["labels"], ["2017"])

    @patch("AI.retrieval.service.fetch_public_body_score")
    @patch("AI.retrieval.service.resolve_public_body_id", return_value=25)
    def test_retriever_adds_public_body_score_context_for_ministry(self, _mock_resolve, mock_fetch_score):
        mock_fetch_score.return_value = {
            "id": 25,
            "responsible_ministry_eng": "Ministry of Planning and Development",
            "code": "MoPD",
            "number_of_indicators": 150,
            "ministry_score_card": {
                "score": "91.63%",
                "score_color": "#6FC327",
                "year": 2018,
                "quarter": "3month",
            },
            "policy_areas": [
                {"policy_area_eng": "Macroeconomic Management", "score": "86.48%"},
            ],
        }
        retriever = MilvusContextRetriever(
            settings=RetrievalSettings(
                milvus_uri="http://localhost:19530",
                collection_name="admas_data",
                embedding_api_base="http://localhost:4001/v1/embeddings",
                embedding_model="BAAI/bge-base-en-v1.5",
                embedding_api_key="empty",
                time_series_api_base="https://time-series.mopd.gov.et/api/mobile",
                time_series_indicator_limit=1,
                retrieval_k=5,
                retrieval_fetch_k=12,
                retrieval_timeout_seconds=30,
            )
        )
        doc = type(
            "Doc",
            (),
            {
                "page_content": "MoPD is responsible for planning and development.",
                "metadata": {"responsible_ministry_eng": "Ministry of Planning and Development"},
            },
        )()
        context, charts = retriever._format_context([doc], "show ministry score for Ministry of Planning and Development in 2018 3month")
        self.assertIn("public_body_score_api:", context)
        self.assertIn("ministry_score: 91.63%", context)
        self.assertEqual(charts, [])
        mock_fetch_score.assert_called_once_with(25, year=2018, quarter="3month", settings=retriever.settings)

    @patch("AI.retrieval.service.fetch_public_body_score")
    @patch("AI.retrieval.service.resolve_public_body_id", return_value=25)
    def test_retriever_exposes_public_body_score_payload_in_sources(self, _mock_resolve, mock_fetch_score):
        payload = {
            "id": 25,
            "responsible_ministry_eng": "Ministry of Planning and Development",
            "code": "MoPD",
            "number_of_indicators": 150,
            "ministry_score_card": {
                "score": "91.63%",
                "score_color": "#6FC327",
                "year": 2018,
                "quarter": "6month",
            },
            "policy_areas": [
                {"policy_area_eng": "Macroeconomic Management", "score": "86.48%", "score_color": "#6FC327"},
            ],
        }
        mock_fetch_score.return_value = payload
        retriever = MilvusContextRetriever(
            settings=RetrievalSettings(
                milvus_uri="http://localhost:19530",
                collection_name="admas_data",
                embedding_api_base="http://localhost:4001/v1/embeddings",
                embedding_model="BAAI/bge-base-en-v1.5",
                embedding_api_key="empty",
                time_series_api_base="https://time-series.mopd.gov.et/api/mobile",
                time_series_indicator_limit=1,
                retrieval_k=5,
                retrieval_fetch_k=12,
                retrieval_timeout_seconds=30,
            )
        )
        doc = type(
            "Doc",
            (),
            {
                "page_content": "MoPD scorecard context",
                "metadata": {"responsible_ministry_eng": "Ministry of Planning and Development"},
            },
        )()
        retriever._format_context([doc], "show the public body scorecard for MoPD")
        source = retriever._source_metadata(doc)
        self.assertEqual(source["public_body_score"]["code"], "MoPD")

    def test_retriever_reranks_docs_by_metadata_match(self):
        retriever = MilvusContextRetriever(
            settings=RetrievalSettings(
                milvus_uri="http://localhost:19530",
                collection_name="admas_data",
                embedding_api_base="http://localhost:4001/v1/embeddings",
                embedding_model="BAAI/bge-base-en-v1.5",
                embedding_api_key="empty",
                time_series_api_base="https://time-series.mopd.gov.et/api/mobile",
                time_series_indicator_limit=1,
                retrieval_k=5,
                retrieval_fetch_k=12,
                retrieval_timeout_seconds=30,
            )
        )
        generic_doc = type(
            "Doc",
            (),
            {
                "page_content": "General macroeconomic note",
                "metadata": {"topic_name": "Macroeconomy"},
            },
        )()
        target_doc = type(
            "Doc",
            (),
            {
                "page_content": "Coffee export indicator",
                "metadata": {"indicator_code": "EXP-02.32", "indicator_eng": "Coffee Export"},
            },
        )()
        ranked = retriever._rerank_docs([generic_doc, target_doc], "coffee export value")
        self.assertEqual(ranked[0].metadata["indicator_eng"], "Coffee Export")


class RetrievalNormalizationTests(TestCase):
    @patch("AI.retrieval.query_normalizer.GeminiTextClient.generate_text", return_value="ethiopia export value 2017")
    def test_amharic_query_is_normalized_for_retrieval(self, _mock_generate):
        out = normalize_retrieval_query("የኢትዮጵያ የውጭ ሽያጭ ዋጋ በ2017")
        self.assertEqual(out, "ethiopia export value 2017")

    def test_english_query_is_not_normalized(self):
        out = normalize_retrieval_query("ethiopia export value 2017")
        self.assertEqual(out, "ethiopia export value 2017")

    def test_indicator_query_resolver_expands_common_metric_aliases(self):
        out = resolve_indicator_query("coffee export trend and gdp contribution")
        self.assertIn("coffee exports", out)
        self.assertIn("gross domestic product", out)

    def test_indicator_query_resolver_expands_ministry_aliases(self):
        out = resolve_indicator_query("moh budget trend")
        self.assertIn("ministry of health", out)


class AIApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="api@example.com",
            username="api_user",
            first_name="API",
            last_name="User",
            password="StrongPass1!",
        )
        self.instance = ChatInstance.objects.create(user=self.user, title="New Chat")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_health_reports_gemini_provider(self):
        response = self.client.get("/api/ai-chat/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["provider"], "gemini")

    @patch("AI.api.MilvusContextRetriever.health", return_value={"ok": True, "collection": "admas_data"})
    def test_dependency_health_reports_milvus(self, _mock_health):
        response = self.client.get("/api/ai-chat/health/dependencies/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["dependencies"]["milvus"]["ok"])

    def test_answer_requires_question(self):
        response = self.client.post(f"/api/ai-chat/answer/{self.instance.id}/", data={}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message"], "QUESTION_REQUIRED")

    @patch("AI.api.AIOrchestrator.handle")
    def test_answer_success_payload(self, mock_handle):
        mock_handle.return_value = OrchestrationResult(
            intent="general_query",
            response_type="text",
            success=True,
            message="<p>Direct answer</p>",
            language="English",
            data={},
            usage={"total_tokens": 10},
            sources=[{"indicator": "Inflation"}],
            charts=[{"type": "line", "label": "Inflation", "labels": ["2023", "2024"], "data": [14.2, 19.8]}],
            context_found=True,
        )
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "What is inflation?"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["answer"], "<p>Direct answer</p>")
        self.assertEqual(response.data["data"]["intent"], "general_query")
        self.assertEqual(response.data["data"]["response_type"], "text")
        self.assertEqual(response.data["data"]["language"], "English")
        self.assertTrue(response.data["data"]["context_found"])
        self.assertEqual(response.data["data"]["sources"][0]["indicator"], "Inflation")
        self.assertEqual(response.data["data"]["charts"][0]["data"], [14.2, 19.8])
        self.assertEqual(QuestionHistory.objects.filter(instance=self.instance).count(), 1)
        self.assertEqual(QuestionHistory.objects.get(instance=self.instance).chart_data[0]["label"], "Inflation")
        self.assertEqual(response.data["data"]["chat_title"], "What is inflation")

    @patch("AI.api.AIOrchestrator.handle")
    def test_answer_updates_generic_instance_title_from_question(self, mock_handle):
        mock_handle.return_value = OrchestrationResult(
            intent="general_query",
            response_type="text",
            success=True,
            message="<p>Direct answer</p>",
            language="English",
            data={},
        )
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "Generate dashboard about coffee export performance"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.title, "Generate dashboard about coffee export performance")

    @patch("AI.api.AIOrchestrator.handle")
    def test_answer_persists_tool_state(self, mock_handle):
        mock_handle.return_value = OrchestrationResult(
            intent="dashboard_generation",
            success=True,
            message='<p>Your dashboard is ready: <a href="https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/">link</a></p>',
            language="English",
            secondary_intents=["time_series_query"],
            data={"share_url": "https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/", "title": "Coffee Export Dashboard"},
            tool_state={
                "intent": "dashboard_generation",
                "topic": "coffee export",
                "resolved_prompt": "generate a dashboard about coffee export",
                "last_tool_result": {"share_url": "https://analytics.mopd.gov.et/share/coffee-export-dashboard-25/"},
            },
        )
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "generate a dashboard about coffee export"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuestionHistory.objects.get(instance=self.instance).tool_data["intent"], "dashboard_generation")

    @patch(
        "AI.api.AIOrchestrator.handle",
        side_effect=OrchestrationError(
            "GENERATION_FAILED",
            "boom",
            intent="general_query",
            language="English",
            message="Gemini text generation failed.",
        ),
    )
    def test_answer_failure_payload(self, _mock_handle):
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "What is inflation?"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["message"], "GENERATION_FAILED")

    @patch(
        "AI.api.AIOrchestrator.handle",
        side_effect=OrchestrationError(
            "RETRIEVAL_FAILED",
            "milvus down",
            intent="time_series_query",
            language="English",
            message="No time-series data was found for this request.",
        ),
    )
    def test_answer_retrieval_failure_payload(self, _mock_handle):
        response = self.client.post(
            f"/api/ai-chat/answer/{self.instance.id}/",
            data={"question": "What is inflation?"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["message"], "RETRIEVAL_FAILED")

    def test_chat_instances_get(self):
        response = self.client.get("/api/ai-chat/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)

    def test_chat_instance_rename(self):
        response = self.client.patch(
            f"/api/ai-chat/instance/{self.instance.id}/",
            data={"title": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["title"], "Renamed")

    def test_chat_instance_delete(self):
        response = self.client.delete(f"/api/ai-chat/delete/{self.instance.id}/")
        self.assertEqual(response.status_code, 200)
        self.instance.refresh_from_db()
        self.assertTrue(self.instance.is_deleted)

    def test_chat_history_returns_rows(self):
        QuestionHistory.objects.create(
            instance=self.instance,
            question="q1",
            response="<p>a1</p>",
            chart_data=[{"type": "line", "label": "GDP", "labels": ["2023", "2024"], "data": [6.1, 8.4]}],
        )
        response = self.client.get(f"/api/ai-chat/history/{self.instance.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["charts"][0]["label"], "GDP")
