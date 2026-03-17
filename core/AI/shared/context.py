import re

from AI.infrastructure.clients import (
    fetch_indicator_time_series,
    fetch_ministry_performance,
    fetch_ministry_score,
)
from .upstream import (
    format_ministry_performance,
    format_ministry_score,
    format_time_series_response,
)


def extract_year_from_question(question: str):
    match = re.search(r"\b(19|20)\d{2}\b", question or "")
    return int(match.group()) if match else None


def build_context_from_docs(docs):
    if not docs:
        return "No relevant indicator found."
    return "\n\n".join(doc.page_content for doc in docs if getattr(doc, "page_content", "").strip()) or "No relevant indicator found."


def build_timeseries_context_from_docs(docs, year=None, max_docs=4):
    if not docs:
        return "No relevant indicator found."

    contexts = []
    for doc in docs[:max_docs]:
        meta = getattr(doc, "metadata", {}) or {}
        indicator_code = meta.get("indicator_code", "")
        name = meta.get("indicator_eng", "")
        topic = meta.get("topic_name", "")
        category = meta.get("category_name", "")
        source = meta.get("source", "")

        response = fetch_indicator_time_series(indicator_code, year=year)
        historical_info = format_time_series_response(response, year)
        metadata_info = (
            "<h3>Indicator Metadata</h3>"
            f"<p><b>Name:</b> {name}</p>"
            f"<p><b>Code:</b> {indicator_code}</p>"
            f"<p><b>Topic:</b> {topic}</p>"
            f"<p><b>Category:</b> {category}</p>"
            f"<p><b>Source:</b> {source}</p>"
        )
        contexts.append(f"{getattr(doc, 'page_content', '')}\n\n{metadata_info}\n\n{historical_info}")

    return "\n<hr/>\n".join(contexts)


def build_ministry_score_context_from_docs(docs, period_requested, max_docs=4):
    contexts = []
    year = (period_requested or {}).get("year")
    quarter = (period_requested or {}).get("quarter")

    for doc in (docs or [])[:max_docs]:
        meta = getattr(doc, "metadata", {}) or {}
        m_id = meta.get("responsible_ministry_id", "")
        payload = fetch_ministry_score(m_id, year=year, quarter=quarter)

        metadata_info = (
            "<h3>Ministry Metadata</h3>"
            f"<p><b>Ministry Name:</b> {meta.get('responsible_ministry_eng', 'Unknown Ministry')}</p>"
            f"<p><b>Code:</b> {meta.get('responsible_ministry_code', 'N/A')}</p>"
            f"<p><b>Entity ID:</b> {m_id}</p>"
        )
        contexts.append(f"{getattr(doc, 'page_content', '')}\n\n{metadata_info}\n\n{format_ministry_score(payload)}")

    return "\n<hr/>\n".join(contexts) or "No relevant ministry found."


def build_ministry_performance_context_from_docs(docs, period_requested, performance_type=None, max_docs=4):
    contexts = []
    year = (period_requested or {}).get("year")
    quarter = (period_requested or {}).get("quarter")

    for doc in (docs or [])[:max_docs]:
        meta = getattr(doc, "metadata", {}) or {}
        m_id = meta.get("responsible_ministry_id", "")
        payload = fetch_ministry_performance(m_id, year=year, quarter=quarter, performance_type=performance_type)

        metadata_info = (
            "<h3>Ministry Metadata</h3>"
            f"<p><b>Ministry Name:</b> {meta.get('responsible_ministry_eng', 'Unknown Ministry')}</p>"
            f"<p><b>Code:</b> {meta.get('responsible_ministry_code', 'N/A')}</p>"
            f"<p><b>Entity ID:</b> {m_id}</p>"
        )
        contexts.append(f"{getattr(doc, 'page_content', '')}\n\n{metadata_info}\n\n{format_ministry_performance(payload)}")

    return "\n<hr/>\n".join(contexts) or "No relevant ministry found."


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)
