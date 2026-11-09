"""Build the AI knowledge base from the live time-series and DPMES APIs.

The retriever matches a question to these records, and their metadata decides
how it is answered: `indicator_code` routes to the time-series tool, which
fetches live values, and `responsible_ministry_id` routes to the DPMES ministry
tools. The records describe indicators and organizations rather than holding
figures, so they only need rebuilding when those change, not on every update
to the data.

Every record carries `kb_source = KB_SOURCE`, so a rebuild can replace exactly
these records without touching documents uploaded through the admin.
"""

import logging
import os
import re

import requests
from langchain_core.documents import Document

from AI.shared.ingestion import enrich_metadata
from dashboard import dpmes2

LOGGER = logging.getLogger(__name__)

KB_SOURCE = "live_api"
# Long technical descriptions drown out the indicator name in the embedding
# (GDP Growth lost to unrelated export records), so keep only their opening.
MAX_DESCRIPTION_CHARS = 220
# Milvus stores the text in a VARCHAR(8192) field counted in bytes; Amharic
# takes three bytes per character, so keep well under the limit.
MAX_TEXT_CHARS = 2000
REQUEST_TIMEOUT = 60


def time_series_base_url():
    return os.getenv("TIME_SERIES_API_BASE", "https://time-series.mopd.gov.et/api/mobile").rstrip("/")


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clip(text):
    return text if len(text) <= MAX_TEXT_CHARS else text[: MAX_TEXT_CHARS - 1].rstrip() + "…"


def _record_id(prefix, key):
    """Stable primary key; Milvus limits it to 100 characters."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(key))
    return f"kb-{prefix}-{safe}"[:100]


def lead_sentence(text):
    """The first sentence, capped, so a description supports the name instead of dominating it."""
    text = _clean(text)
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if len(sentence) > MAX_DESCRIPTION_CHARS:
        sentence = sentence[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return sentence


def _second_name(primary, other):
    """The Amharic name, when the API gives one that differs from the English."""
    other = _clean(other)
    return other if other and other != primary else ""


def _document(page_content, metadata):
    meta = {key: value for key, value in metadata.items() if value not in (None, "")}
    meta["kb_source"] = KB_SOURCE
    return Document(page_content=_clip(page_content), metadata=enrich_metadata(meta))


# --- Time series -----------------------------------------------------------


def fetch_time_series_topics(session=None):
    """Every topic with its categories and (nested) indicators."""
    session = session or requests.Session()
    base = time_series_base_url()
    response = session.get(f"{base}/topic-list/", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    topics = []
    for topic in response.json().get("data") or []:
        detail = session.get(f"{base}/topic-detail/{topic['id']}/", timeout=REQUEST_TIMEOUT)
        detail.raise_for_status()
        topics.append(detail.json().get("data") or {})
    return topics


def indicator_documents(topics):
    """One record per indicator code, including nested child indicators.

    Indicators without a code are skipped: the time-series tool looks values up
    by code, so such a record could be retrieved but never answered.
    """
    records = {}

    def walk(indicators, topic, category, parent):
        for item in indicators or []:
            title = _clean(item.get("title_ENG"))
            code = _clean(item.get("code"))
            if code and code not in records:
                records[code] = _indicator_document(item, title, code, topic, category, parent)
            walk(item.get("children"), topic, category, title or parent)

    for topic in topics:
        for category in topic.get("categories") or []:
            if category.get("is_deleted"):
                continue
            walk(category.get("indicators"), topic, category, "")

    return [(_record_id("indicator", code), doc) for code, doc in records.items()]


def _indicator_document(item, title, code, topic, category, parent):
    topic_name = _clean(topic.get("title_ENG"))
    category_name = _clean(category.get("name_ENG"))
    amharic = _second_name(title, item.get("title_AMH"))
    unit = _clean(item.get("measurement_units"))
    frequency = _clean(item.get("frequency"))
    source = _clean(item.get("source"))
    # Lead with the name: it is what questions ask about.
    lines = [title, f"Ethiopia indicator: {title}" + (f" ({amharic})" if amharic else "") + f". Code {code}."]
    lines.append(f"Topic: {topic_name}; category: {category_name}" + (f"; part of {parent}" if parent else "") + ".")
    details = [part for part in (
        f"unit {unit}" if unit and unit != "None" else "",
        f"{frequency} data" if frequency else "",
        f"source {source}" if source else "",
    ) if part]
    if details:
        lines.append("Measured as " + ", ".join(details) + ".")
    description = lead_sentence(item.get("description"))
    if description:
        lines.append(description)

    return _document("\n".join(lines), {
        "doc_type": "indicator",
        "indicator_code": code,
        "indicator_eng": title,
        "indicator_amh": amharic,
        "topic_name": topic_name,
        "category_name": category_name,
        "category_code": _clean(category.get("code")),
        "parent_indicator": parent,
        "measurement_units": unit if unit != "None" else "",
        "frequency": frequency,
        "source": source or "Time Series",
    })


# --- DPMES -----------------------------------------------------------------


def fetch_dpmes(period):
    """Organizations and policy areas with the goals under each."""
    organizations = dpmes2.child_organizations(period) or []
    org_scorecards = {
        org["id"]: dpmes2.organization_scorecard(org["id"], period) or {}
        for org in organizations
        if org.get("is_active", True)
    }
    policy_areas = dpmes2.policy_area_scores(period) or []
    area_scorecards = {
        area["id"]: dpmes2.policy_area_scorecard(area["id"], period) or {}
        for area in policy_areas
    }
    return organizations, org_scorecards, policy_areas, area_scorecards


def _names(items, limit=40):
    names = [_clean(item.get("name") or item.get("trans_name")) for item in items or []]
    names = [name for name in names if name]
    extra = len(names) - limit
    return "; ".join(names[:limit]) + (f"; and {extra} more" if extra > 0 else "")


def organization_documents(organizations, scorecards):
    documents = []
    for org in organizations:
        if org.get("id") not in scorecards:
            continue
        name = _clean(org.get("name") or org.get("trans_name"))
        code = _clean(org.get("code"))
        areas = scorecards[org["id"]].get("policy_areas") or []

        # Identity, not subject matter: listing every goal here made ministry
        # records match topical questions (GDP pulled in the National Bank).
        # Goals have their own records.
        lines = [name + (f" ({code})" if code else "")]
        amharic = _second_name(name, org.get("name_eth"))
        lines.append(f"Ethiopian public body (ministry or agency): {name}" + (f", also known as {amharic}" if amharic else "") + ".")
        lines.append(f"{name} performance in DPMES: overall score, policy area scores, and KPIs that are on track, "
                     "in progress, weak or have no data.")
        if areas:
            lines.append(f"Policy areas: {_names(areas, limit=8)}.")

        documents.append((_record_id("ministry", org["id"]), _document("\n".join(lines), {
            "doc_type": "ministry",
            "responsible_ministry_id": str(org["id"]),
            "responsible_ministry_eng": name,
            "responsible_ministry_code": code,
            "source": "DPMES",
        })))
    return documents


def policy_area_documents(policy_areas, scorecards):
    documents = []
    for area in policy_areas:
        name = _clean(area.get("name") or area.get("trans_name"))
        code = _clean(area.get("code"))
        goals = (scorecards.get(area.get("id")) or {}).get("goals") or []
        lines = [name + (f" ({code})" if code else "")]
        amharic = _second_name(name, area.get("name_eth"))
        lines.append(f"Ethiopia national policy area: {name}" + (f", also known as {amharic}" if amharic else "") + ".")
        if goals:
            lines.append(f"Strategic goals: {_names(goals, limit=10)}.")

        documents.append((_record_id("policy-area", area["id"]), _document("\n".join(lines), {
            "doc_type": "policy_area",
            "policy_area_id": str(area["id"]),
            "policy_area_eng": name,
            "policy_area_name": name,
            "policy_area_code": code,
            "source": "DPMES",
        })))
    return documents


def goal_documents(policy_areas, scorecards):
    documents, seen = [], set()
    for area in policy_areas:
        area_name = _clean(area.get("name") or area.get("trans_name"))
        for goal in (scorecards.get(area.get("id")) or {}).get("goals") or []:
            if goal.get("id") in seen:
                continue
            seen.add(goal.get("id"))
            name = _clean(goal.get("name") or goal.get("trans_name"))
            code = _clean(goal.get("code"))
            lines = [name + (f" ({code})" if code else "")]
            amharic = _second_name(name, goal.get("name_eth"))
            lines.append(f"Ethiopia national strategic goal: {name}" + (f", also known as {amharic}" if amharic else "") + ".")
            lines.append(f"Policy area: {area_name}.")

            documents.append((_record_id("goal", goal["id"]), _document("\n".join(lines), {
                "doc_type": "goal",
                "goal_id": str(goal["id"]),
                "goal_name": name,
                "goal_eng": name,
                "goal_code": code,
                "policy_area_eng": area_name,
                "source": "DPMES",
            })))
    return documents


def build_documents(*, include_dpmes=True, period=None, log=LOGGER.info):
    """Fetch everything and return a list of (record id, Document)."""
    log("Fetching time-series topics…")
    topics = fetch_time_series_topics()
    documents = indicator_documents(topics)
    log(f"  {len(documents)} indicators from {len(topics)} topics")

    if include_dpmes:
        if not dpmes2.is_configured():
            raise dpmes2.DPMES2Error("DPMES2_API_KEY is not set.")
        period = period or {"year": dpmes2.current_ethiopian_year() - 1}
        log(f"Fetching DPMES organizations and policy areas for {period}…")
        organizations, org_cards, areas, area_cards = fetch_dpmes(period)
        for label, built in (
            ("ministries", organization_documents(organizations, org_cards)),
            ("policy areas", policy_area_documents(areas, area_cards)),
            ("goals", goal_documents(areas, area_cards)),
        ):
            documents.extend(built)
            log(f"  {len(built)} {label}")

    return documents
