"""Suggested next questions, shown under an answer in the web chat.

After an answer the gateway model proposes up to three short questions the user
might ask next ("Compare with 2016", "Show it by region"), in the question's
language and answerable from Admas AI's three sources. They are a nicety: any
failure gives no suggestions, never an error. The mobile app is not sent them.
"""

import re

from ai.engine import llm, verify
from ai.engine.planner import detect_request_language

MAX_SUGGESTIONS = 3
MAX_CHARS = 80
ANSWER_CHARS = 1200

PROMPT = """You suggest follow-up questions for Admas AI, the assistant of Ethiopia's Ministry of National Strategy.
It answers from three sources: the national time-series database (economic and social indicators by year, quarter or month), DPMES (performance scores and KPIs of ministries, agencies, policy areas and strategic goals), and Ethiopia's national SDG platform (SDG indicators, often by region, sex, age or urban/rural).

Given the user's question and the answer they got, suggest up to {count} questions they are likely to ask next, such as another year, a comparison, a breakdown, the weakest or strongest items, a related indicator, or a short explanation.
Rules:
- Each must be answerable from those sources and must not repeat the question just asked.
- Short (at most 8 words) and specific: name the indicator, ministry, goal or year instead of "it".
- Written as the user would type them, in {language}. No numbering, no quotation marks."""

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_SUGGESTIONS}},
    "required": ["questions"],
}


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(html or ""))).strip()


def _key(text):
    return re.sub(r"[\W_]+", " ", text.lower()).strip()


def clean(raw, question):
    """Keep short, distinct, well-formed suggestions that differ from the question."""
    seen = {_key(question)}
    kept = []
    for item in raw or []:
        text = re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", _plain(item)).strip().strip("\"'“”‘’")
        key = _key(text)
        if not text or len(text) > MAX_CHARS or key in seen or verify.foreign_script(text):
            continue
        seen.add(key)
        kept.append(text)
    return kept[:MAX_SUGGESTIONS]


async def suggest(question, answer_html):
    language = detect_request_language(question)
    messages = [
        {"role": "system", "content": PROMPT.format(count=MAX_SUGGESTIONS, language=language)},
        {"role": "user", "content": f"Question: {str(question or '')[:500]}\n\n"
                                    f"Answer: {_plain(answer_html)[:ANSWER_CHARS]}"},
    ]
    try:
        raw = await llm.json_completion(messages, SCHEMA, name="followups", max_tokens=160, temperature=0.3)
    except llm.LLMError:
        return []
    return clean(raw.get("questions"), question)
