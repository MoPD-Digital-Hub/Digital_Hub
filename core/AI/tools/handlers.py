from AI.shared import (
    build_context_from_docs,
    build_ministry_performance_context_from_docs,
    build_ministry_score_context_from_docs,
    build_timeseries_context_from_docs,
    extract_year_from_question,
)
from .helpers import max_docs, normalize_year, resolve_period, resolve_performance_type
from .runtime import mcp, register_runtime_tool


@register_runtime_tool(
    description="Fetch and format economic or social indicator time-series context, including trend history by year."
)
@mcp.tool(
    description="Fetch and format economic or social indicator time-series context, including trend history by year."
)
def get_time_series_context(*, question, docs, arguments, llm):
    year = normalize_year(arguments.get("year")) if arguments else None
    if year is not None:
        year = int(year)
    if year is None:
        year = extract_year_from_question(question)
    return build_timeseries_context_from_docs(docs, year=year, max_docs=max_docs())


@register_runtime_tool(
    description="Fetch ministry or agency score context for a requested year and reporting period."
)
@mcp.tool(
    description="Fetch ministry or agency score context for a requested year and reporting period."
)
def get_ministry_score_context(*, question, docs, arguments, llm):
    return build_ministry_score_context_from_docs(docs, resolve_period(question, arguments), max_docs=max_docs())


@register_runtime_tool(
    description="Fetch filtered ministry KPI performance context such as weak, on-track, in-progress, or missing-data indicators."
)
@mcp.tool(
    description="Fetch filtered ministry KPI performance context such as weak, on-track, in-progress, or missing-data indicators."
)
def get_ministry_performance_context(*, question, docs, arguments, llm):
    period = resolve_period(question, arguments)
    performance_type = resolve_performance_type(question, arguments)
    return build_ministry_performance_context_from_docs(
        docs,
        period,
        performance_type=performance_type,
        max_docs=max_docs(),
    )


@register_runtime_tool(description="Fetch policy area or sector-level context for score-based questions.")
@mcp.tool(description="Fetch policy area or sector-level context for score-based questions.")
def get_policy_area_context(*, question, docs, arguments, llm):
    return build_context_from_docs(docs)


@register_runtime_tool(description="Fetch strategic goal or national target context for goal-focused questions.")
@mcp.tool(description="Fetch strategic goal or national target context for goal-focused questions.")
def get_goal_context(*, question, docs, arguments, llm):
    return build_context_from_docs(docs)


@register_runtime_tool(
    description="Use the general retrieved DPMES context when no specialized score or time-series tool clearly applies."
)
@mcp.tool(
    description="Use the general retrieved DPMES context when no specialized score or time-series tool clearly applies."
)
def get_general_context(*, question, docs, arguments, llm):
    return build_context_from_docs(docs)
