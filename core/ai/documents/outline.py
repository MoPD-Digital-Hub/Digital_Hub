"""The content of a document, written by the model as a structured outline.

The model only fills in this outline (title, key messages, sections with their
points and chosen chart or table, conclusion, speaker notes); the builders lay
it out. It writes from the fetched facts only, like a chat answer, and its
numbers are checked the same way.
"""

import json
import re
from datetime import date

from ai.documents import datasets as datasets_module
from ai.documents import design
from ai.engine import amharic, compose, llm, verify

SECTIONS = {"pptx": (3, 6), "docx": (3, 5), "pdf": (3, 5)}

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "key_messages": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "sections": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "points": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "visual": {"type": "string", "enum": ["chart", "table", "none"]},
                    "dataset": {"type": "integer"},
                    "notes": {"type": "string"},
                },
                "required": ["heading", "points", "visual"],
            },
        },
        "conclusion": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    },
    "required": ["title", "key_messages", "sections", "conclusion"],
}

PROMPT = """You are Admas AI, the analyst of Ethiopia's Ministry of National Strategy (MoNS, formerly the Ministry of Planning and Development).
Write the content of a {format_name} for senior officials, from the facts below. The layout, charts and tables are made automatically from your outline. Today is {today}.

Rules:
- Use only the facts given. Never state a number that is not in them; write figures exactly as they appear, with their unit and period. If something the user asked for is not in the facts, leave it out.
- title: at most 10 words, naming the subject and period. subtitle: one short line (scope or source).
- key_messages: 3 messages, each one sentence of at most 25 words, each led by the most important figure.
- sections: {min_sections} to {max_sections}, in a logical order (overview, trend, comparison or breakdown, implications). Each has a heading of at most 8 words, 2 to 4 points of at most 25 words each, and a visual:
  "chart" or "table" with the number of the dataset that supports it (datasets are numbered from 0), or "none". Use each dataset at most once; prefer a chart for a time series and a table for scores or lists.
  notes: 2 or 3 sentences the presenter can say about the section.
- conclusion: 2 or 3 points: what the figures mean for policy and what to watch next, without new numbers.
- Years: data from the time-series database and DPMES is in the Ethiopian calendar ({calendar}); data marked "calendar": "Gregorian" (the SDG platform) and web pages use Gregorian years ({gregorian}).
- Name the source of the figures in the subtitle or a point (for example "according to DPMES").
- Plain text only: no HTML, no markdown, no numbering, no bullet characters.
- Write everything in {language}."""


def _clean_text(text, limit):
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text or ""))).strip()
    # A bullet or list number ("1. ", "2) "), not the start of a figure ("10.41% …").
    text = re.sub(r"^(?:[-*•▪◦]\s*|\d+[.)]\s+)", "", text)
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def _clean(raw, datasets, document_format):
    used = set()
    sections = []
    low, high = SECTIONS[document_format]
    for section in (raw.get("sections") or [])[:high]:
        heading = _clean_text(section.get("heading"), 90)
        points = [p for p in (_clean_text(p, 220) for p in section.get("points") or []) if p][:4]
        if not heading or not points:
            continue
        visual, index = section.get("visual"), section.get("dataset")
        dataset = None
        if visual in ("chart", "table") and isinstance(index, int) and 0 <= index < len(datasets) and index not in used:
            if visual == "chart" and datasets[index].get("chart") or visual == "table" and datasets[index].get("table"):
                dataset = index
            elif datasets[index].get("chart") or datasets[index].get("table"):
                visual = "chart" if datasets[index].get("chart") else "table"
                dataset = index
        if dataset is None:
            visual = "none"
        else:
            used.add(dataset)
        sections.append({"heading": heading, "points": points, "visual": visual, "dataset": dataset,
                         "notes": _clean_text(section.get("notes"), 600)})
    # Datasets the writer left out still belong in the document: give each a section.
    for index, dataset in enumerate(datasets):
        if index not in used and len(sections) < high:
            sections.append({"heading": _clean_text(dataset["title"], 90), "points": [],
                             "visual": "chart" if dataset.get("chart") else "table", "dataset": index, "notes": ""})
    return {
        "title": _clean_text(raw.get("title"), 110) or "Admas AI",
        "subtitle": _clean_text(raw.get("subtitle"), 160),
        "key_messages": [m for m in (_clean_text(m, 220) for m in raw.get("key_messages") or []) if m][:3],
        "sections": sections,
        "conclusion": [c for c in (_clean_text(c, 220) for c in raw.get("conclusion") or []) if c][:3],
        "min_sections": low,
    }


def texts(outline):
    """Every piece of text in the outline, for checks."""
    parts = [outline["title"], outline["subtitle"], *outline["key_messages"], *outline["conclusion"]]
    for section in outline["sections"]:
        parts += [section["heading"], section["notes"], *section["points"]]
    return [p for p in parts if p]


def _scrub(outline):
    outline["title"] = verify.scrub_foreign(outline["title"])
    outline["subtitle"] = verify.scrub_foreign(outline["subtitle"])
    outline["key_messages"] = [verify.scrub_foreign(m) for m in outline["key_messages"]]
    outline["conclusion"] = [verify.scrub_foreign(c) for c in outline["conclusion"]]
    for section in outline["sections"]:
        section["heading"] = verify.scrub_foreign(section["heading"])
        section["notes"] = verify.scrub_foreign(section["notes"])
        section["points"] = [verify.scrub_foreign(p) for p in section["points"]]
    return outline


def messages(question, document_format, language, datasets, results, pages, conversation="", avoid=()):
    low, high = SECTIONS[document_format]
    system = PROMPT.format(
        format_name=design.FORMAT_NAMES["English"][document_format], today=date.today().isoformat(),
        min_sections=low, max_sections=high, language=language,
        calendar=compose.CALENDAR_NOTES.get(language, compose.CALENDAR_NOTES["English"]),
        gregorian=compose.GREGORIAN_NOTES.get(language, compose.GREGORIAN_NOTES["English"]))
    if language == "Amharic":
        system += amharic.rules()
    facts = compose.facts(results, []) if results else "[]"
    user = (f"{conversation}Request: {question}\n\nDatasets for charts and tables (JSON):\n"
            f"{_summary_or_none(datasets)}\n\nFacts (JSON):\n{facts[:14000]}")
    if pages:
        user += f"\n\nWeb pages (JSON; cite them in points as [1], [2]):\n{compose.web_pages(pages)[:9000]}"
    if avoid:
        numbers = ", ".join(f"{n:g}" for n in avoid)
        user += (f"\n\nA previous draft used these numbers, which are not in the facts: {numbers}. Do not write "
                 "them, and do not count, round or estimate: name the items and give their exact values instead.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _summary_or_none(datasets):
    return datasets_module.summary(datasets) if datasets else "[]"


async def write(question, document_format, language, datasets, results=(), pages=(), conversation="", avoid=()):
    """The cleaned outline. Raises llm.LLMError when the gateway fails.

    `avoid`: numbers a previous draft used that are not in the facts.
    """
    request = messages(question, document_format, language, datasets, results, pages, conversation, avoid)
    raw = await llm.json_completion(request, SCHEMA, name="document_outline", max_tokens=2500, temperature=0.2)
    outline = _clean(raw, datasets, document_format)
    if language == "Amharic" and verify.foreign_script(" ".join(texts(outline))):
        retry = await llm.json_completion(request, SCHEMA, name="document_outline", max_tokens=2500, temperature=0.4)
        outline = _clean(retry, datasets, document_format)
        outline = _scrub(outline)
    return outline


def as_json(outline):
    return json.dumps(outline, ensure_ascii=False)
