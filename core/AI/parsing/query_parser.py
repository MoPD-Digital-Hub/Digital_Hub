import json
import re
from langchain_core.prompts import PromptTemplate
from .constants import DEFAULT_QUARTER, VALID_PERFORMANCE_KEYS, VALID_QUARTERS, YEAR_PATTERN
from .entity_aliases import (
    has_goal_reference,
    has_institution_reference,
    has_policy_area_reference,
    has_time_series_reference,
)
from .rules import (
    QUARTER_PATTERNS,
    contains_time_series_vocabulary,
    match_performance_vocabulary,
)

TOOL_NAME_TIME_SERIES = "get_time_series_context"
TOOL_NAME_MINISTRY_SCORE = "get_ministry_score_context"
TOOL_NAME_MINISTRY_PERFORMANCE = "get_ministry_performance_context"
TOOL_NAME_POLICY_AREA = "get_policy_area_context"
TOOL_NAME_GOAL = "get_goal_context"
TOOL_NAME_GENERAL = "get_general_context"

VALID_TOOL_NAMES = {
    TOOL_NAME_TIME_SERIES,
    TOOL_NAME_MINISTRY_SCORE,
    TOOL_NAME_MINISTRY_PERFORMANCE,
    TOOL_NAME_POLICY_AREA,
    TOOL_NAME_GOAL,
    TOOL_NAME_GENERAL,
}

PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
You classify user questions ONLY for the DPMES system.

Choose ONE tool name:

get_ministry_score_context → Use this if the question is about a specific Ministry, Government Body, or Agency (e.g., "Ministry of Health", "Planning Commission", "Public Service Authority"). 
- This includes their performance, scores, rankings, or status for any specific year/quarter.
- If a Ministry name is mentioned, this tool ALWAYS takes priority over get_time_series_context.

get_ministry_performance_context → Use this when the user's goal is to see a FILTERED LIST or CATEGORIZATION of specific indicators/KPIs based on how they are performing.
- Identifying specific successes or failures within a ministry.
- Requests for qualitative status groups (e.g., searching for what is "on track," "lagging," "missing data," or "performing poorly").
- Focuses on the "Why" and "What" (the specific items) rather than the "How much" (the total score).
- Example: "Give me the list of weak KPIs for a ministry," or "Which health goals are meeting their targets?"

get_time_series_context → Use this ONLY for specific economic or social indicators/metrics (e.g., "GDP", "Inflation", "Export value", "Unemployment rate").
- Use this when the user asks for historical trends or values of a specific numeric variable.

get_policy_area_context → Use this for thematic sectors rather than institutions (e.g., "How is the Health Sector doing?" vs "How is the Ministry of Health doing?").

get_goal_context → Strategic goal achievement, Ten Year Development Plan goals, or high-level national targets.

get_general_context → Greetings, general chat, or topics unrelated to DPMES data.

Question:
{question}

Return ONLY the tool name.
"""
)

def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())


def _contains_any(text: str, phrases) -> bool:
    return any(phrase in text for phrase in phrases)


def _extract_json_block(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _normalize_tool_name(raw_text: str) -> str:
    text = (raw_text or "").upper()

    normalized = (raw_text or "").strip()
    if normalized in VALID_TOOL_NAMES:
        return normalized

    for key in VALID_TOOL_NAMES:
        if re.search(rf"\b{re.escape(key.upper())}\b", text):
            return key

    return TOOL_NAME_GENERAL


def _normalize_quarter(value):
    quarter = (value or DEFAULT_QUARTER)
    quarter = str(quarter).strip().lower()
    if quarter in VALID_QUARTERS:
        return quarter
    return DEFAULT_QUARTER


def _classify_intent_rule_based(question: str, docs=None) -> str | None:
    text = _normalize_question(question)
    if not text:
        return TOOL_NAME_GENERAL

    has_ministry = has_institution_reference(text, docs=docs)
    has_policy_area = has_policy_area_reference(text, docs=docs)
    has_goal = has_goal_reference(text, docs=docs)
    has_timeseries = (
        has_time_series_reference(text, docs=docs)
        or contains_time_series_vocabulary(text)
        or bool(YEAR_PATTERN.search(text))
    )
    has_performance_status = extract_performance_type(None, text) is not None

    if has_ministry and has_performance_status:
        return TOOL_NAME_MINISTRY_PERFORMANCE
    if has_ministry:
        return TOOL_NAME_MINISTRY_SCORE
    if has_policy_area:
        return TOOL_NAME_POLICY_AREA
    if has_goal:
        return TOOL_NAME_GOAL
    if has_timeseries:
        return TOOL_NAME_TIME_SERIES
    return None


def classify_intent(llm, question: str, docs=None) -> str:
    rule_based_intent = _classify_intent_rule_based(question, docs=docs)
    if rule_based_intent:
        return rule_based_intent

    if llm is None:
        return TOOL_NAME_GENERAL

    try:
        result = llm.invoke(PROMPT.format(question=question))
        return _normalize_tool_name(getattr(result, "content", ""))
    except Exception:
        return TOOL_NAME_GENERAL

DPMES_EXTRACTION_YEAR_QUARTER_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
Analyze the following user question about the DPMES system. 
Extract the Year, Quarter and the Reporting Period.

Normalize the "period" according to these rules:
- "3 month", "1st quarter", "Q1" -> "3month"
- "6 month", "half year", "2nd quarter", "Q2" -> "6month"
- "9 month", "3rd quarter", "Q3" -> "9month"
- "Annual", "Full year", "12 month", "4th quarter", "Q4" -> "12month"

Question: {question}

Return ONLY raw JSON:
{{
  "year": "YYYY or null",
  "quarter": "period or null"
}}
"""
)

def extract_year_quarter(llm, question: str) -> dict:
    """
    Parses the question to extract normalized year and quarter.
    Returns a dictionary, e.g., {"year": "2017", "quarter": "9month"}
    """
    question_text = str(question or "")
    year_match = YEAR_PATTERN.search(question_text)
    detected_year = year_match.group(0) if year_match else None

    for pattern, value in QUARTER_PATTERNS:
        if pattern.search(question_text):
            return {"year": detected_year, "quarter": value}

    if llm is None:
        return {"year": detected_year, "quarter": DEFAULT_QUARTER}

    try:
        result = llm.invoke(DPMES_EXTRACTION_YEAR_QUARTER_PROMPT.format(question=question))
        clean_content = _extract_json_block(getattr(result, "content", ""))
        data = json.loads(clean_content)
        year = data.get("year")
        if year is not None:
            year = str(year).strip()
            if not re.fullmatch(r"(19|20)\d{2}", year):
                year = None
        return {
            "year": year,
            "quarter": _normalize_quarter(data.get("quarter"))
        }
    except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
        return {"year": detected_year, "quarter": DEFAULT_QUARTER}

DPMES_PERFORMANCE_STATUS_EXTRACTOR = PromptTemplate(
    input_variables=["question"],
    template="""
Analyze the user's question and map their performance-related language to exactly ONE of the system keys.

### System Keys:
- "on_track": (good, success, achieved, excellent, best, meeting targets)
- "in_progress": (average, satisfactory, moving, developing, mid-range)
- "weak_performance": (bad, poor, critical, failing, behind, low scores)
- "no_data": (missing, not reported, unknown, blank, unsubmitted)

### Important Rules:
- Ignore the year or quarter (e.g., "2018", "Q1"). Only extract the performance status.
- If the user is asking for general performance without a specific status (e.g., "How is this ministry performing?"), return null.
- Return ONLY the key name. No explanation.

Question: {question}
Return (on_track/in_progress/weak_performance/no_data/null):"""
)

def extract_performance_type(llm, question: str):
    text = _normalize_question(question)
    matched_key = match_performance_vocabulary(text)
    if matched_key:
        return matched_key

    if llm is None:
        return None

    try:
        result = llm.invoke(DPMES_PERFORMANCE_STATUS_EXTRACTOR.format(question=question))
        content = result.content.strip().lower()
    except Exception:
        return None
    
    for key in VALID_PERFORMANCE_KEYS:
        if re.search(rf"\b{re.escape(key)}\b", content):
            return key
            
    return None 
