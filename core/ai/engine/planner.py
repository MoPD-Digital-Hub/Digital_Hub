"""Turn a question into a plan: what kind of question it is and which data to fetch."""

import re
from dataclasses import dataclass, field
from html import unescape

from ai.infrastructure.translation import detect_request_language
from ai.engine import llm
from ai.engine.tools import TOOLS

MAX_CALLS = 4
HISTORY_TURNS = 3

ENTITY_ARGS = ("indicator", "organization", "policy_area", "goal")

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["data", "general", "greeting", "out_of_scope"]},
        "calls": {
            "type": "array",
            "maxItems": MAX_CALLS,
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "enum": list(TOOLS)},
                    "indicator": {"type": "string"},
                    "organization": {"type": "string"},
                    "policy_area": {"type": "string"},
                    "goal": {"type": "string"},
                    "year": {"type": "integer"},
                    "quarter": {"type": "integer", "minimum": 1, "maximum": 4},
                    "performance": {"type": "string", "enum": ["all", "on_track", "in_progress", "weak", "no_data"]},
                    "order": {"type": "string", "enum": ["top", "bottom"]},
                },
                "required": ["tool"],
            },
        },
    },
    "required": ["kind", "calls"],
}

SYSTEM_PROMPT = """You plan data lookups for Admas AI, the assistant of Ethiopia's Ministry of National Strategy (MoNS, formerly the Ministry of Planning and Development).
It answers from two sources: the national time-series database (economic and social indicators) and DPMES (performance scores of ministries/agencies, policy areas, strategic goals and their KPIs).

Tools:
{tools}

Return JSON with:
- kind: "data" if answering needs figures from the tools; "general" for a conceptual question that needs no figures (e.g. what an indicator means); "greeting" for greetings or thanks; "out_of_scope" for anything unrelated to Ethiopia's statistics, planning or government performance.
- calls: the lookups for a "data" question, otherwise []. One call per thing asked about, at most {max_calls}.

Rules for calls:
- Name entities in English, as specifically as the question allows ("GDP growth", "year-on-year general inflation", "Ministry of Health"). Translate Amharic names into English.
- Use the conversation to resolve follow-ups like "what about 2016?" or "and the weak ones?".
- Set year only when the question gives one, and quarter (1-4) only when it names a quarter.
- Scores, ratings, rankings and KPIs of ministries or agencies come from DPMES tools; quantities, rates and trends of the economy or society come from indicator_series.
- performance: "weak" for weak, poor, failing or lagging KPIs; "on_track" for good or achieved; "in_progress"; "no_data" for missing or unreported; "all" otherwise.
- order: "bottom" when asked for the worst or lowest, otherwise "top".

Examples:
Q: What is Ethiopia's GDP growth?
{{"kind": "data", "calls": [{{"tool": "indicator_series", "indicator": "GDP growth"}}]}}
Q: How did the Ministry of Health score in 2017, and which of its KPIs are weak?
{{"kind": "data", "calls": [{{"tool": "organization_score", "organization": "Ministry of Health", "year": 2017}}, {{"tool": "organization_kpis", "organization": "Ministry of Health", "performance": "weak", "year": 2017}}]}}
Q: Which ministries performed worst?
{{"kind": "data", "calls": [{{"tool": "rank_organizations", "order": "bottom"}}]}}
Q: What does inflation mean?
{{"kind": "general", "calls": []}}"""


@dataclass
class Plan:
    kind: str
    language: str
    calls: list = field(default_factory=list)

    def as_dict(self):
        return {"kind": self.kind, "language": self.language, "calls": self.calls}


def _plain(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(html or "")))).strip()


def _conversation(history):
    turns = [t for t in history if t.get("question")][-HISTORY_TURNS:]
    if not turns:
        return ""
    lines = []
    for turn in turns:
        lines.append(f"User: {turn['question']}")
        if turn.get("response"):
            lines.append(f"Assistant: {_plain(turn['response'])[:300]}")
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _clean_calls(raw_calls):
    calls = []
    for call in raw_calls or []:
        tool = TOOLS.get(call.get("tool"))
        if tool is None:
            continue
        # A call is only usable when every entity it needs was named.
        if any(not str(call.get(arg) or "").strip() for arg in tool.entities):
            continue
        calls.append({key: value for key, value in call.items() if value not in (None, "")})
    return calls[:MAX_CALLS]


async def plan(question, history=()):
    language = detect_request_language(question)
    tools = "\n".join(f"- {tool.name}: {tool.description}" for tool in TOOLS.values())
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools=tools, max_calls=MAX_CALLS)},
        {"role": "user", "content": f"{_conversation(history)}Question: {question}"},
    ]
    raw = await llm.json_completion(messages, SCHEMA, name="plan")
    kind = raw.get("kind") if raw.get("kind") in ("data", "general", "greeting", "out_of_scope") else "general"
    calls = _clean_calls(raw.get("calls")) if kind == "data" else []
    if kind == "data" and not calls:
        kind = "general"
    return Plan(kind=kind, language=language, calls=calls)
