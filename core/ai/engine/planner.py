"""Turn a question into a plan: what kind of question it is and which data to fetch."""

import re
from dataclasses import dataclass, field
from html import unescape

from ai.engine import llm
from ai.engine.tools import TOOLS
from integrations.websearch import client as websearch

MAX_CALLS = 4
HISTORY_TURNS = 5

ENTITY_ARGS = ("indicator", "organization", "policy_area", "goal", "sdg_indicator", "sdg_goal")

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["data", "web", "general", "greeting", "out_of_scope"]},
        "search_query": {"type": "string"},
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
                    "sdg_indicator": {"type": "string"},
                    "sdg_goal": {"type": "string"},
                    "breakdown": {"type": "string", "enum": ["region", "sex", "age", "location", "education", "wealth"]},
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
It answers from three sources: the national time-series database (economic and social indicators), DPMES (performance scores of ministries/agencies, policy areas, strategic goals and their KPIs), and the national SDG platform (Ethiopia's Sustainable Development Goal indicators, mostly from surveys, with regional and sex breakdowns).

Tools:
{tools}

Return JSON with:
{kinds}
- calls: the lookups for a "data" question, otherwise []. One call per thing asked about, at most {max_calls}.

Rules for calls:
- Name entities in English, as specifically as the question allows ("GDP growth", "year-on-year general inflation", "Ministry of Health"). Translate Amharic names into English.
- Use the conversation to resolve follow-ups like "what about 2016?" or "and the weak ones?".
- A follow-up that only asks to explain, simplify, summarise, interpret or translate an earlier answer ("explain that simply", "summarise this for a briefing", "what does that mean?", "answer that in Amharic") needs no new figures: kind "general", calls [].
- A request for the answer's language ("in Amharic", "in English") is not a topic: plan the rest of the question as usual.
- Set year only when the question gives one, and quarter (1-4) only when it names a quarter.
- Scores, ratings, rankings and KPIs of ministries or agencies come from DPMES tools; quantities, rates and trends of the economy or society come from indicator_series.
- Use the SDG tools when the question mentions the SDGs, a goal or indicator number (SDG 4, 3.1.1), or asks about an SDG topic the time-series database does not cover well: poverty headcount, stunting and malnutrition, school completion and learning, access to water and sanitation, gender equality, or a breakdown by region or sex. For a topic both cover (GDP, inflation, maternal mortality, electricity access) use indicator_series unless the SDGs are mentioned. sdg_goal is for overall progress on a goal; sdg_indicator for one indicator. Name SDG indicators by what they measure, or by number when given.
- breakdown: "region" for by region or regional differences, "sex" for male/female, "location" for urban/rural; otherwise leave it out.
- performance: "weak" for weak, poor, failing or lagging KPIs; "on_track" for good or achieved; "in_progress"; "no_data" for missing or unreported; "all" otherwise.
- order: "bottom" when asked for the worst or lowest, otherwise "top".

Examples:
Q: What is Ethiopia's GDP growth?
{{"kind": "data", "calls": [{{"tool": "indicator_series", "indicator": "GDP growth"}}]}}
Q: How did the Ministry of Health score in 2017, and which of its KPIs are weak?
{{"kind": "data", "calls": [{{"tool": "organization_score", "organization": "Ministry of Health", "year": 2017}}, {{"tool": "organization_kpis", "organization": "Ministry of Health", "performance": "weak", "year": 2017}}]}}
Q: How is Ethiopia progressing on SDG 4?
{{"kind": "data", "calls": [{{"tool": "sdg_goal", "sdg_goal": "SDG 4"}}]}}
Q: What is the poverty rate by region?
{{"kind": "data", "calls": [{{"tool": "sdg_indicator", "sdg_indicator": "poverty headcount index", "breakdown": "region"}}]}}
Q: Which ministries performed worst?
{{"kind": "data", "calls": [{{"tool": "rank_organizations", "order": "bottom"}}]}}
Q: What does inflation mean?
{{"kind": "general", "calls": []}}{web_examples}"""

KINDS = """- kind: "data" if answering needs figures from the tools; "general" for a conceptual question that needs no figures (e.g. what an indicator means); "greeting" for greetings or thanks; "out_of_scope" for anything unrelated to Ethiopia's statistics, planning or government performance."""

# With web search on, general questions that need current or outside facts are searched.
WEB_KINDS = """- kind: "data" if answering needs figures from the tools; "web" for a general question that needs current or specific facts the tools do not hold: news and recent events, international organisations, agreements and programmes, other countries, laws, institutions and people in public roles; "general" for a conceptual question you can answer without looking anything up (e.g. what an indicator means); "greeting" for greetings or thanks; "out_of_scope" for requests an analyst assistant should not answer (personal matters, anything harmful, writing code, jokes or stories).
- Never use "web" for Ethiopia's official statistics, the performance of its ministries, policy areas or goals, or its SDG indicators: those are "data".
- search_query: for "web", a short English web search query (3 to 10 words) for what the question needs, with "Ethiopia" when it is about Ethiopia; otherwise "". Translate Amharic into English."""

WEB_EXAMPLES = """
Q: What is the IMF Extended Credit Facility for Ethiopia?
{{"kind": "web", "search_query": "IMF Extended Credit Facility Ethiopia", "calls": []}}
Q: What did the latest African Union summit decide?
{{"kind": "web", "search_query": "African Union summit latest decisions", "calls": []}}"""


@dataclass
class Plan:
    kind: str
    language: str
    calls: list = field(default_factory=list)
    search_query: str = ""

    def as_dict(self):
        plan = {"kind": self.kind, "language": self.language, "calls": self.calls}
        if self.search_query:
            plan["search_query"] = self.search_query
        return plan


AMHARIC_SCRIPT = re.compile(r"[\u1200-\u137F]")


# An explicit request for a language wins over the question's script:
# "answer in Amharic", "translate it to Amharic", "Amharic please", "በአማርኛ".
REPLY_WORDS = r"(?:answer|reply|respond|response|write|explain|say|tell|give|show|translate|make|put)"
LANGUAGE_REQUESTS = {
    "Amharic": re.compile(
        r"\b(?:in|into|to|using|use)\s+amharic\b|\bamharic\s+(?:please|version|translation|language)\b"
        rf"|\b{REPLY_WORDS}\b[^.?!]*\bamharic\b|^\W*amharic\W*$|በአማርኛ",
        re.IGNORECASE),
    "English": re.compile(
        r"\b(?:in|into|to|using|use)\s+english\b|\benglish\s+(?:please|version|translation|language)\b"
        rf"|\b{REPLY_WORDS}\b[^.?!]*\benglish\b|^\W*english\W*$|በእንግሊዝኛ",
        re.IGNORECASE),
}


def requested_language(text):
    """The language the text explicitly asks the answer to be in, or None."""
    text = str(text or "")
    for language, pattern in LANGUAGE_REQUESTS.items():
        if pattern.search(text):
            return language
    return None


def detect_request_language(text):
    """An explicit request ("in Amharic") first; then Amharic script gets Amharic, anything else English."""
    return requested_language(text) or ("Amharic" if AMHARIC_SCRIPT.search(str(text or "")) else "English")


def without_language_request(question):
    """The question to plan: "What is GDP growth? answer in Amharic" -> "What is GDP growth?".

    A question that is only a language request ("make the response in Amharic")
    is kept as it is: it asks for the previous answer again.
    """
    text = str(question or "")
    for pattern in LANGUAGE_REQUESTS.values():
        text = pattern.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return text if len(re.sub(r"\W", "", text)) >= 3 else str(question or "")


def reply_language(question, history=()):
    """The answer's language, keeping a language the user asked for earlier in the chat.

    "Answer in Amharic" once, and the chat's later English-script questions get
    Amharic answers too, until the user asks for English.
    """
    asked = requested_language(question)
    if asked:
        return asked
    if AMHARIC_SCRIPT.search(str(question or "")):
        return "Amharic"
    for turn in reversed(list(history)):
        asked = requested_language(turn.get("question"))
        if asked:
            return asked
    return "English"


def _plain(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(html or "")))).strip()


def conversation(history, answer_chars=300):
    """The chat's recent turns as plain text, for the planner and the writer.

    Each earlier answer is cut to `answer_chars`: the planner needs only the
    topic, the writer a little more (its first figures) to refer back to.
    """
    turns = [t for t in history if t.get("question")][-HISTORY_TURNS:]
    if not turns:
        return ""
    lines = []
    for turn in turns:
        lines.append(f"User: {turn['question']}")
        if turn.get("response"):
            lines.append(f"Assistant: {_plain(turn['response'])[:answer_chars]}")
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
    language = reply_language(question, history)
    tools = "\n".join(f"- {tool.name}: {tool.description}" for tool in TOOLS.values())
    web = websearch.enabled()
    prompt = SYSTEM_PROMPT.format(tools=tools, max_calls=MAX_CALLS, kinds=WEB_KINDS if web else KINDS,
                                  web_examples=WEB_EXAMPLES.replace("{{", "{").replace("}}", "}") if web else "")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"{conversation(history)}Question: {without_language_request(question)}"},
    ]
    raw = await llm.json_completion(messages, SCHEMA, name="plan")
    kind = raw.get("kind") if raw.get("kind") in ("data", "web", "general", "greeting", "out_of_scope") else "general"
    calls = _clean_calls(raw.get("calls")) if kind == "data" else []
    if kind == "data" and not calls:
        kind = "general"
    search_query = ""
    if kind == "web":
        if web:
            search_query = re.sub(r"\s+", " ", str(raw.get("search_query") or "")).strip()[:200] or question[:200]
        else:
            kind = "general"
    return Plan(kind=kind, language=language, calls=calls, search_query=search_query)
