import logging
from dataclasses import dataclass

from .client import GeminiClientError, GeminiTextClient
from .config import get_gemini_settings
from .prompting import GeminiPromptBuilder
from AI.retrieval import MilvusContextRetriever

LOGGER = logging.getLogger("AI.gemini.service")


@dataclass
class ChatGenerationResult:
    answer: str
    language: str
    usage: dict | None = None
    sources: list | None = None
    charts: list | None = None
    context_found: bool = False


class GeminiChatService:
    def __init__(self, client=None, prompt_builder=None, settings=None, retriever=None):
        self.settings = settings or get_gemini_settings()
        self.client = client or GeminiTextClient(self.settings)
        self.prompt_builder = prompt_builder or GeminiPromptBuilder()
        self.retriever = retriever or MilvusContextRetriever()

    def generate(self, *, question: str, history_records=None, context: str | None = None):
        retrieval = self.retriever.retrieve(question)
        return self.generate_from_retrieval(
            question=question,
            history_records=history_records or [],
            retrieval=retrieval,
            context=context,
        )

    def generate_from_retrieval(self, *, question: str, history_records=None, retrieval=None, context: str | None = None):
        retrieval = retrieval or self.retriever.retrieve(question)
        selected_charts = self._select_relevant_charts(question, retrieval.charts, retrieval.sources)
        final_context = context if context is not None else retrieval.context
        messages, language = self.prompt_builder.build_messages(
            question=question,
            history_records=self._trim_history(history_records or []),
            context=final_context,
        )
        response = self.client.generate(messages)
        return ChatGenerationResult(
            answer=response["text"],
            language=language,
            usage=response.get("usage"),
            sources=retrieval.sources,
            charts=selected_charts,
            context_found=bool(final_context.strip()) if isinstance(final_context, str) else False,
        )

    def iter_answer_chunks(self, *, question: str, history_records=None, context: str | None = None):
        result = self.generate(question=question, history_records=history_records, context=context)
        for chunk in self.client.iter_chunks(result.answer):
            yield chunk
        return result

    async def stream_answer(self, *, question: str, history_records=None, context: str | None = None):
        retrieval = self.retriever.retrieve(question)
        async for event in self.stream_from_retrieval(
            question=question,
            history_records=history_records or [],
            retrieval=retrieval,
            context=context,
        ):
            yield event

    async def stream_from_retrieval(self, *, question: str, history_records=None, retrieval=None, context: str | None = None):
        retrieval = retrieval or self.retriever.retrieve(question)
        selected_charts = self._select_relevant_charts(question, retrieval.charts, retrieval.sources)
        final_context = context if context is not None else retrieval.context
        messages, language = self.prompt_builder.build_messages(
            question=question,
            history_records=self._trim_history(history_records or []),
            context=final_context,
        )
        async for event in self.client.stream_generate(messages):
            yield {
                "text": event.get("text") or "",
                "language": language,
                "usage": event.get("usage"),
                "sources": retrieval.sources,
                "charts": selected_charts,
                "context_found": bool(final_context.strip()) if isinstance(final_context, str) else False,
            }

    def _trim_history(self, history_records):
        limit = self.settings.max_history_questions
        if limit <= 0:
            return []
        normalized_records = []
        for item in history_records or []:
            question = str(item.get("question") or "").strip()
            response = str(item.get("response") or "").strip()
            if not question:
                continue
            normalized_records.append(
                {
                    "question": question,
                    "response": response,
                }
            )
        return normalized_records[-limit:]

    def _select_relevant_charts(self, question: str, charts, sources=None):
        available = [chart for chart in (charts or []) if self._chart_has_enough_points(chart)]
        if not available:
            return []
        if self._question_explicitly_disables_chart(question):
            return []
        if self._question_targets_scorecard(question, sources):
            return []
        return available[:1]

    def _chart_has_enough_points(self, chart) -> bool:
        labels = chart.get("labels") if isinstance(chart, dict) else []
        data = chart.get("data") if isinstance(chart, dict) else []
        return isinstance(labels, list) and isinstance(data, list) and len(labels) >= 4 and len(labels) == len(data)

    def _question_explicitly_disables_chart(self, question: str) -> bool:
        text = str(question or "").strip().lower()
        if not text:
            return False

        disable_terms = (
            "no chart",
            "don't generate chart",
            "do not generate chart",
            "don't generate the chart",
            "do not generate the chart",
            "without chart",
            "summary only",
            "only summary",
            "text only",
            "only text",
            "no graph",
            "don't show graph",
            "do not show graph",
            "don't show the chart",
            "do not show the chart",
            "no visualization",
            "do not visualize",
            "don't visualize",
            "just summarize",
            "only summarize",
            "without graph",
            "አታቀርብ ቻርት",
            "ቻርት አይኖር",
            "ያለ ቻርት",
            "ማጠቃለያ ብቻ",
            "ጽሑፍ ብቻ",
            "ግራፍ አታሳይ",
            "ያለ ግራፍ",
        )
        if any(term in text for term in disable_terms):
            return True

        return ("chart" in text or "graph" in text) and any(
            phrase in text for phrase in ("do not", "don't", "without", "only", "just", "no ")
        )

    def _question_targets_scorecard(self, question: str, sources=None) -> bool:
        text = str(question or "").strip().lower()
        score_terms = (
            "scorecard",
            "score card",
            "ministry score",
            "public body score",
            "policy area score",
            "ministry performance score",
            "public body performance score",
            "የሚኒስቴር ውጤት",
            "ስኮርካርድ",
            "የተቋም ውጤት",
        )
        if any(term in text for term in score_terms):
            return True
        return any(isinstance(source, dict) and source.get("public_body_score") for source in (sources or []))
