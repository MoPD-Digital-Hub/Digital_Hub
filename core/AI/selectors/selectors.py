from django.conf import settings
from AI.classifiers import classify_intent, extract_performance_type, extract_year_quarter
from AI.domain import INTENTS
from AI.shared import (
    build_context_from_docs,
    build_ministry_performance_context_from_docs,
    build_ministry_score_context_from_docs,
    build_timeseries_context_from_docs,
    extract_year_from_question,
)


def resolve_intent(llm, question, docs):
    return classify_intent(llm, question)


def build_context_for_intent(intent, llm, question, docs):
    max_docs = max(1, getattr(settings, "AI_MAX_RETRIEVAL_DOCS", 4))
    if intent == INTENTS["TIME_SERIES"]:
        year_requested = extract_year_from_question(question)
        return build_timeseries_context_from_docs(docs, year=year_requested, max_docs=max_docs)

    if intent == INTENTS["MINISTRY_SCORE"]:
        period_requested = extract_year_quarter(llm, question)
        return build_ministry_score_context_from_docs(docs, period_requested, max_docs=max_docs)

    if intent == INTENTS["MINISTRY_PERFORMANCE"]:
        period_requested = extract_year_quarter(llm, question)
        performance_requested = extract_performance_type(llm, question)
        return build_ministry_performance_context_from_docs(
            docs, period_requested, performance_requested, max_docs=max_docs
        )

    return build_context_from_docs(docs)
