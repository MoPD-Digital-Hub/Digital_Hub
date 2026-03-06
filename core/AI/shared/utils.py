"""Compatibility shim for legacy imports.

Prefer importing from AI.shared package-level exports directly.
"""

from .chat import (
    invoke_chat_once,
    is_greeting,
    normalize_history_for_messages,
    run_chain,
    run_chain_stream,
    select_system_rule,
)
from .constants import AI_RESPONSE_FAILED_HTML, AI_TEMPORARILY_UNAVAILABLE_HTML, REQUIRED_METADATA_KEYS_ANY
from .context import (
    build_context_from_docs,
    build_ministry_performance_context_from_docs,
    build_ministry_score_context_from_docs,
    build_timeseries_context_from_docs,
    extract_year_from_question,
    format_docs,
)
from .ingestion import process_document, split_json, text_splitter
from .upstream import (
    fetch_indicator_time_series,
    fetch_ministry_performance,
    fetch_ministry_score,
    format_ministry_performance,
    format_ministry_score,
    format_time_series_response,
)

__all__ = [
    "AI_RESPONSE_FAILED_HTML",
    "AI_TEMPORARILY_UNAVAILABLE_HTML",
    "REQUIRED_METADATA_KEYS_ANY",
    "split_json",
    "process_document",
    "text_splitter",
    "run_chain",
    "select_system_rule",
    "normalize_history_for_messages",
    "invoke_chat_once",
    "run_chain_stream",
    "is_greeting",
    "extract_year_from_question",
    "build_context_from_docs",
    "build_timeseries_context_from_docs",
    "build_ministry_score_context_from_docs",
    "build_ministry_performance_context_from_docs",
    "format_docs",
    "fetch_indicator_time_series",
    "fetch_ministry_score",
    "fetch_ministry_performance",
    "format_time_series_response",
    "format_ministry_score",
    "format_ministry_performance",
]
