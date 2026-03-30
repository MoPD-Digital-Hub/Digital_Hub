import logging

from AI.gemini.language import detect_language
from AI.gemini.service import GeminiChatService
from AI.gemini.client import GeminiClientError
from AI.query_preprocessing import QueryPreprocessor
from AI.retrieval import RetrievalError

from .classifier import IntentClassifier
from .context import ConversationStateResolver
from .dashboard import DashboardGenerationService, DashboardServiceError
from .formatter import dashboard_failure_message, dashboard_success_message, time_series_failure_message
from .result import OrchestrationResult
from .scorecard import ScorecardQueryService
from .time_series import TimeSeriesQueryError, TimeSeriesQueryService

LOGGER = logging.getLogger("AI.orchestration")
ALLOWED_RESPONSE_TYPES = {"text", "scorecard", "time_series", "table", "not_found", "dashboard_link"}


class OrchestrationError(Exception):
    def __init__(self, code: str, detail: str, *, intent: str, language: str, message: str | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.intent = intent
        self.language = language
        self.message = message or detail


class AIOrchestrator:
    def __init__(self, classifier=None, text_service=None, time_series_service=None, dashboard_service=None, scorecard_service=None):
        self.preprocessor = QueryPreprocessor()
        self.classifier = classifier or IntentClassifier(preprocessor=self.preprocessor)
        self.context_resolver = ConversationStateResolver(self.classifier, preprocessor=self.preprocessor)
        self.text_service = text_service or GeminiChatService()
        self.time_series_service = time_series_service or TimeSeriesQueryService(text_service=self.text_service)
        self.dashboard_service = dashboard_service or DashboardGenerationService()
        self.scorecard_service = scorecard_service or ScorecardQueryService()

    def handle(self, *, question: str, history_records=None) -> OrchestrationResult:
        language = detect_language(question)
        resolved = self.context_resolver.resolve(question, history_records or [])
        intent = resolved.primary_intent
        secondary_intents = resolved.secondary_intents
        effective_question = resolved.resolved_prompt or question
        try:
            if intent == "dashboard_generation":
                return self._handle_dashboard(question, language, resolved)
            if intent == "scorecard_query":
                return self._handle_scorecard(effective_question, history_records or [], language, secondary_intents, resolved)
            if intent == "time_series_query":
                return self._handle_time_series(effective_question, history_records or [], language, secondary_intents, resolved)
            return self._handle_general(effective_question, history_records or [], secondary_intents, resolved)
        except DashboardServiceError as exc:
            LOGGER.exception("Dashboard generation failed")
            raise OrchestrationError(
                "DASHBOARD_FAILED",
                str(exc),
                intent="dashboard_generation",
                language=language,
                message=dashboard_failure_message(language),
            ) from exc
        except TimeSeriesQueryError as exc:
            LOGGER.exception("Time-series query failed")
            raise OrchestrationError(
                "TIME_SERIES_FAILED",
                str(exc),
                intent="time_series_query",
                language=language,
                message=time_series_failure_message(language),
            ) from exc
        except RetrievalError as exc:
            LOGGER.exception("Retrieval failed during orchestration")
            raise OrchestrationError(
                "RETRIEVAL_FAILED",
                str(exc),
                intent=intent,
                language=language,
                message=time_series_failure_message(language) if intent == "time_series_query" else "Milvus retrieval failed.",
            ) from exc
        except GeminiClientError as exc:
            LOGGER.exception("Gemini generation failed during orchestration")
            raise OrchestrationError(
                "GENERATION_FAILED",
                str(exc),
                intent=intent,
                language=language,
                message="Gemini text generation failed.",
            ) from exc

    async def stream(self, *, question: str, history_records=None):
        language = detect_language(question)
        resolved = self.context_resolver.resolve(question, history_records or [])
        intent = resolved.primary_intent
        secondary_intents = resolved.secondary_intents
        effective_question = resolved.resolved_prompt or question
        try:
            if intent == "dashboard_generation":
                result = self._handle_dashboard(question, language, resolved)
                yield self._event_from_result(result)
                return

            if intent == "scorecard_query":
                result = self._handle_scorecard(effective_question, history_records or [], language, secondary_intents, resolved)
                yield self._event_from_result(result)
                return

            if intent == "time_series_query":
                try:
                    retrieval = self.time_series_service.retrieve(effective_question, preprocessed=resolved.preprocessed)
                except TypeError:
                    retrieval = self.time_series_service.retrieve(effective_question)
                async for event in self.text_service.stream_from_retrieval(
                    question=effective_question,
                    history_records=history_records or [],
                    retrieval=retrieval,
                ):
                    response_payload = self._finalize_response_payload(
                        intent=intent,
                        question=effective_question,
                        answer=event.get("text") or "",
                        proposed_type="table" if self._prefers_table_response(effective_question) else "time_series",
                        sources=event.get("sources") or [],
                        charts=event.get("charts") or [],
                    )
                    yield {
                        "intent": intent,
                        "response_type": response_payload["response_type"],
                        "secondary_intents": secondary_intents,
                        "text": event.get("text") or "",
                        "language": event.get("language") or language,
                        "usage": event.get("usage"),
                        "sources": event.get("sources") or [],
                        "charts": event.get("charts") or [],
                        "context_found": event.get("context_found", False),
                        "data": response_payload,
                        "tool_state": {
                            "intent": intent,
                            "response_type": response_payload["response_type"],
                            "response_payload": response_payload,
                            "topic": resolved.topic,
                            "resolved_prompt": resolved.resolved_prompt or effective_question,
                            "language": event.get("language") or language,
                            "last_tool_result": {
                                "sources": event.get("sources") or [],
                                "charts": event.get("charts") or [],
                                "context_found": event.get("context_found", False),
                                "usage": event.get("usage") or {},
                            },
                        },
                    }
                return

            async for event in self.text_service.stream_answer(
                question=effective_question,
                history_records=history_records or [],
                context=self._follow_up_context_text(resolved),
            ):
                response_payload = self._finalize_response_payload(
                    intent="general_query",
                    question=effective_question,
                    answer=event.get("text") or "",
                    proposed_type="text",
                    sources=event.get("sources") or [],
                    charts=event.get("charts") or [],
                )
                yield {
                    "intent": intent,
                    "response_type": response_payload["response_type"],
                    "secondary_intents": secondary_intents,
                    "text": event.get("text") or "",
                    "language": event.get("language") or language,
                    "usage": event.get("usage"),
                    "sources": event.get("sources") or [],
                    "charts": event.get("charts") or [],
                    "context_found": event.get("context_found", False),
                    "data": response_payload,
                    "tool_state": {
                        "intent": "general_query",
                        "response_type": response_payload["response_type"],
                        "response_payload": response_payload,
                        "topic": resolved.topic,
                        "resolved_prompt": resolved.resolved_prompt or effective_question,
                        "language": event.get("language") or language,
                        "last_tool_result": {
                            "sources": event.get("sources") or [],
                            "charts": event.get("charts") or [],
                            "context_found": event.get("context_found", False),
                            "usage": event.get("usage") or {},
                        },
                    },
                }
        except DashboardServiceError as exc:
            LOGGER.exception("Dashboard generation failed")
            raise OrchestrationError(
                "DASHBOARD_FAILED",
                str(exc),
                intent="dashboard_generation",
                language=language,
                message=dashboard_failure_message(language),
            ) from exc
        except TimeSeriesQueryError as exc:
            LOGGER.exception("Time-series query failed")
            raise OrchestrationError(
                "TIME_SERIES_FAILED",
                str(exc),
                intent="time_series_query",
                language=language,
                message=time_series_failure_message(language),
            ) from exc
        except RetrievalError as exc:
            LOGGER.exception("Retrieval failed during orchestration")
            raise OrchestrationError(
                "RETRIEVAL_FAILED",
                str(exc),
                intent=intent,
                language=language,
                message=time_series_failure_message(language) if intent == "time_series_query" else "Milvus retrieval failed.",
            ) from exc
        except GeminiClientError as exc:
            LOGGER.exception("Gemini generation failed during orchestration")
            raise OrchestrationError(
                "GENERATION_FAILED",
                str(exc),
                intent=intent,
                language=language,
                message="Gemini text generation failed.",
            ) from exc

    def _handle_general(self, question: str, history_records, secondary_intents, resolved) -> OrchestrationResult:
        result = self.text_service.generate(
            question=question,
            history_records=history_records,
            context=self._follow_up_context_text(resolved),
        )
        response_payload = self._finalize_response_payload(
            intent="general_query",
            question=question,
            answer=result.answer,
            proposed_type="text",
            sources=result.sources or [],
            charts=result.charts or [],
        )
        return OrchestrationResult(
            intent="general_query",
            response_type=response_payload["response_type"],
            secondary_intents=secondary_intents,
            success=True,
            message=result.answer,
            language=result.language,
            data=response_payload,
            tool_state={
                "intent": "general_query",
                "response_type": response_payload["response_type"],
                "response_payload": response_payload,
                "topic": resolved.topic,
                "resolved_prompt": resolved.resolved_prompt or question,
                "language": result.language,
                "last_tool_result": {
                    "sources": result.sources or [],
                    "charts": result.charts or [],
                    "context_found": result.context_found,
                    "usage": result.usage or {},
                },
            },
            usage=result.usage,
            sources=result.sources or [],
            charts=result.charts or [],
            context_found=result.context_found,
        )

    def _handle_time_series(self, question: str, history_records, language: str, secondary_intents, resolved) -> OrchestrationResult:
        try:
            result = self.time_series_service.answer(
                question=question,
                history_records=history_records,
                preprocessed=resolved.preprocessed,
            )
        except TypeError:
            result = self.time_series_service.answer(question=question, history_records=history_records)
        response_payload = self._finalize_response_payload(
            intent="time_series_query",
            question=question,
            answer=result.answer,
            proposed_type="table" if self._prefers_table_response(question) else "time_series",
            sources=result.sources or [],
            charts=result.charts or [],
        )
        return OrchestrationResult(
            intent="time_series_query",
            response_type=response_payload["response_type"],
            secondary_intents=secondary_intents,
            success=True,
            message=result.answer,
            language=result.language or language,
            data=response_payload,
            tool_state={
                "intent": "time_series_query",
                "response_type": response_payload["response_type"],
                "response_payload": response_payload,
                "topic": resolved.topic,
                "resolved_prompt": resolved.resolved_prompt or question,
                "language": result.language or language,
                "last_tool_result": {
                    "sources": result.sources or [],
                    "charts": result.charts or [],
                    "context_found": result.context_found,
                },
            },
            usage=result.usage,
            sources=result.sources or [],
            charts=result.charts or [],
            context_found=result.context_found,
        )

    def _handle_scorecard(self, question: str, history_records, language: str, secondary_intents, resolved) -> OrchestrationResult:
        try:
            result = self.scorecard_service.answer(
                question=question,
                history_records=history_records,
                language=language,
                preprocessed=resolved.preprocessed,
            )
        except TypeError:
            result = self.scorecard_service.answer(question=question, history_records=history_records, language=language)
        response_payload = self._finalize_response_payload(
            intent="scorecard_query",
            question=question,
            answer=result.answer,
            proposed_type="scorecard" if result.found else "not_found",
            sources=result.sources or [],
            charts=[],
            scorecard=result.scorecard or {},
        )
        return OrchestrationResult(
            intent="scorecard_query",
            response_type=response_payload["response_type"],
            secondary_intents=secondary_intents,
            success=True,
            message=result.answer,
            language=result.language or language,
            data=response_payload,
            tool_state={
                "intent": "scorecard_query",
                "response_type": response_payload["response_type"],
                "response_payload": response_payload,
                "topic": resolved.topic,
                "resolved_prompt": resolved.resolved_prompt or question,
                "language": result.language or language,
                "last_tool_result": {
                    "scorecard": result.scorecard or {},
                    "sources": result.sources or [],
                    "charts": [],
                    "context_found": result.context_found,
                },
            },
            usage=None,
            sources=result.sources or [],
            charts=[],
            context_found=result.context_found,
        )

    def _handle_dashboard(self, question: str, language: str, resolved) -> OrchestrationResult:
        existing_dashboard = resolved.existing_dashboard or {}
        if resolved.return_existing_link and existing_dashboard.get("share_url"):
            dashboard = existing_dashboard
        else:
            dashboard = self.dashboard_service.create_dashboard(resolved.resolved_prompt or question)
        response_payload = self._finalize_response_payload(
            intent="dashboard_generation",
            question=question,
            answer=dashboard_success_message(dashboard.get("title"), dashboard.get("share_url"), language),
            proposed_type="dashboard_link",
            sources=[],
            charts=[],
            extra_data={"dashboard": dashboard},
        )
        return OrchestrationResult(
            intent="dashboard_generation",
            response_type=response_payload["response_type"],
            secondary_intents=resolved.secondary_intents,
            success=True,
            message=response_payload["summary"],
            language=language,
            data=response_payload,
            tool_state={
                "intent": "dashboard_generation",
                "response_type": response_payload["response_type"],
                "response_payload": response_payload,
                "secondary_intents": resolved.secondary_intents,
                "pending_action": "create_dashboard",
                "topic": resolved.topic,
                "resolved_prompt": resolved.resolved_prompt or question,
                "query_variants": list((resolved.preprocessed.variants if resolved.preprocessed else []) or []),
                "last_tool_used": "dashboard_generation",
                "last_tool_result": dashboard,
                "language": language,
            },
            usage=None,
            sources=[],
            charts=[],
            context_found=False,
        )

    def _event_from_result(self, result: OrchestrationResult) -> dict:
        return {
            "intent": result.intent,
            "response_type": result.response_type,
            "secondary_intents": result.secondary_intents,
            "text": result.message,
            "language": result.language,
            "usage": result.usage,
            "sources": result.sources or [],
            "charts": result.charts or [],
            "context_found": result.context_found,
            "data": result.data or {},
            "tool_state": result.tool_state or {},
        }

    def _finalize_response_payload(
        self,
        *,
        intent: str,
        question: str,
        answer: str,
        proposed_type: str,
        sources: list[dict],
        charts: list[dict],
        scorecard: dict | None = None,
        extra_data: dict | None = None,
    ) -> dict:
        payload = self._build_response_payload(
            intent=intent,
            question=question,
            answer=answer,
            response_type=proposed_type,
            sources=sources,
            charts=charts,
            scorecard=scorecard,
            extra_data=extra_data,
        )
        return self._validate_response_payload(payload, question=question, answer=answer, sources=sources)

    def _build_response_payload(
        self,
        *,
        intent: str,
        question: str,
        answer: str,
        response_type: str,
        sources: list[dict],
        charts: list[dict],
        scorecard: dict | None = None,
        extra_data: dict | None = None,
    ) -> dict:
        title = self._title_from_question(question)
        summary = answer
        primary_domain = self._primary_domain(sources)
        if intent == "scorecard_query" or response_type in {"scorecard", "not_found"}:
            primary_domain = "DPMES"
        elif response_type in {"time_series", "table"}:
            primary_domain = "TSMS"
        data = {
            "primary_domain": primary_domain,
            "supporting_context": self._supporting_context_from_sources(sources),
        }
        if response_type == "scorecard" and scorecard:
            score = dict(scorecard.get("ministry_score_card") or {})
            title = scorecard.get("responsible_ministry_eng") or "Scorecard"
            data.update(
                {
                    "entity_name": title,
                    "overall_score": score.get("score"),
                    "score_color": score.get("score_color"),
                    "period": {
                        "year": score.get("year"),
                        "quarter": score.get("quarter"),
                    },
                    "policy_areas": list(scorecard.get("policy_areas") or []),
                    "description": answer,
                    "code": scorecard.get("code"),
                }
            )
        elif response_type == "time_series":
            data.update(
                {
                    "series": self._series_from_charts(charts),
                    "trend_summary": answer,
                }
            )
        elif response_type == "table":
            data.update(
                {
                    "series": self._series_from_charts(charts),
                    "table": self._table_from_charts(charts),
                }
            )
        elif response_type == "dashboard_link":
            title = str((extra_data or {}).get("dashboard", {}).get("title") or "Analytics Dashboard")
            data.update(
                {
                    "url": str((extra_data or {}).get("dashboard", {}).get("share_url") or ""),
                    "dashboard": dict((extra_data or {}).get("dashboard") or {}),
                }
            )
        elif response_type == "not_found":
            title = "No Results"
            data.update({"text": answer})
        else:
            data.update({"text": answer})

        if extra_data:
            data.update(dict(extra_data))

        payload = {
            "response_type": response_type if response_type in ALLOWED_RESPONSE_TYPES else "text",
            "title": title,
            "summary": summary,
            "data": data,
        }
        return payload

    def _validate_response_payload(self, payload: dict, *, question: str, answer: str, sources: list[dict]) -> dict:
        safe_payload = dict(payload or {})
        response_type = str(safe_payload.get("response_type") or "text").strip().lower()
        data = dict(safe_payload.get("data") or {})
        if response_type not in ALLOWED_RESPONSE_TYPES:
            response_type = "text"

        if response_type == "scorecard":
            has_score = bool(data.get("overall_score"))
            has_policy_area = bool(data.get("policy_area")) or bool(data.get("policy_areas"))
            if not (has_score or has_policy_area):
                response_type = "text"
        elif response_type == "time_series":
            if not self._has_series_data(data):
                response_type = "text"
        elif response_type == "table":
            table = dict(data.get("table") or {})
            if not (isinstance(table.get("columns"), list) and isinstance(table.get("rows"), list) and table.get("rows")):
                response_type = "text"

        if response_type == "text":
            return {
                "response_type": "text",
                "title": str(safe_payload.get("title") or self._title_from_question(question)),
                "summary": str(safe_payload.get("summary") or answer),
                "data": {
                    "text": answer,
                    "primary_domain": data.get("primary_domain") or self._primary_domain(sources),
                    "supporting_context": data.get("supporting_context") or self._supporting_context_from_sources(sources),
                },
            }

        safe_payload["response_type"] = response_type
        safe_payload["title"] = str(safe_payload.get("title") or self._title_from_question(question))
        safe_payload["summary"] = str(safe_payload.get("summary") or answer)
        safe_payload["data"] = data
        return safe_payload

    def _series_from_charts(self, charts: list[dict]) -> list[dict]:
        series = []
        for chart in charts or []:
            if not isinstance(chart, dict):
                continue
            labels = list(chart.get("labels") or [])
            values = list(chart.get("data") or [])
            if not labels or not values:
                continue
            series.append(
                {
                    "label": chart.get("label") or "Series",
                    "type": chart.get("type") or "line",
                    "labels": labels,
                    "values": values,
                }
            )
        return series

    def _table_from_charts(self, charts: list[dict]) -> dict:
        series = self._series_from_charts(charts)
        if not series:
            return {"columns": [], "rows": []}
        first = series[0]
        rows = []
        for label, value in zip(first.get("labels") or [], first.get("values") or []):
            rows.append([label, value])
        return {"columns": ["Period", "Value"], "rows": rows}

    def _has_series_data(self, data: dict) -> bool:
        series = list((data or {}).get("series") or [])
        for item in series:
            if isinstance(item, dict) and item.get("labels") and item.get("values"):
                return True
        return False

    def _prefers_table_response(self, question: str) -> bool:
        text = str(question or "").strip().lower()
        return any(term in text for term in ("table", "tabular", "rows", "columns"))

    def _supporting_context_from_sources(self, sources: list[dict]) -> dict:
        for source in sources or []:
            if not isinstance(source, dict):
                continue
            public_body = source.get("public_body_score")
            if isinstance(public_body, dict):
                return {
                    "responsible_public_body": {
                        "name": public_body.get("responsible_ministry_eng"),
                        "code": public_body.get("code"),
                    }
                }
            if source.get("ministry"):
                return {
                    "responsible_public_body": {
                        "name": source.get("ministry"),
                        "code": source.get("ministry_id"),
                    }
                }
        return {}

    def _primary_domain(self, sources: list[dict]) -> str:
        for source in sources or []:
            if isinstance(source, dict) and source.get("public_body_score"):
                return "DPMES"
        return "knowledge_base"

    def _title_from_question(self, question: str) -> str:
        text = str(question or "").strip()
        return text[:80] if text else "Admas AI"

    def _follow_up_context_text(self, resolved) -> str | None:
        context = dict(getattr(resolved, "follow_up_context", {}) or {})
        if not resolved.context_dependent or not context:
            return None
        lines = []
        topic = str(context.get("topic") or "").strip()
        intent = str(context.get("intent") or "").strip()
        response = str(context.get("response") or "").strip()
        if topic:
            lines.append(f"Previous topic: {topic}")
        if intent:
            lines.append(f"Previous intent: {intent}")
        tool_data = dict(context.get("tool_data") or {})
        dashboard = dict(tool_data.get("last_tool_result") or {})
        sources = list((tool_data.get("last_tool_result") or {}).get("sources") or [])
        if dashboard.get("title"):
            lines.append(f"Dashboard title: {dashboard.get('title')}")
        if dashboard.get("share_url"):
            lines.append(f"Dashboard link: {dashboard.get('share_url')}")
        if sources:
            source_labels = []
            for source in sources[:5]:
                if isinstance(source, dict):
                    label = source.get("indicator") or source.get("topic") or source.get("indicator_code")
                    if label:
                        source_labels.append(str(label))
            if source_labels:
                lines.append(f"Previous sources: {', '.join(source_labels)}")
        charts = list(context.get("charts") or [])
        if charts:
            chart = charts[0]
            labels = ", ".join(str(item) for item in (chart.get("labels") or [])[:4])
            values = ", ".join(str(item) for item in (chart.get("data") or [])[:4])
            if labels and values:
                lines.append(f"Previous chart sample labels: {labels}")
                lines.append(f"Previous chart sample values: {values}")
        lines.append("Use the previous response and carried context as trusted context for the follow-up answer.")
        if response:
            lines.append("Previous assistant response:")
            lines.append(response)
        return "\n".join(lines).strip() or None
