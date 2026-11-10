"""Fetch the indicator and organization lists the catalog is built from."""

import os
import re

import requests

from integrations.dpmes import client as dpmes_client

REQUEST_TIMEOUT = 60
# Long technical descriptions drown out the indicator name in the embedding,
# so the catalog keeps only their opening.
MAX_DESCRIPTION_CHARS = 220


def time_series_base_url():
    return os.getenv("TIME_SERIES_API_BASE", "https://time-series.mopd.gov.et/api/mobile").rstrip("/")


def lead_sentence(text):
    """The first sentence, capped, so a description supports the name instead of dominating it."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if len(sentence) > MAX_DESCRIPTION_CHARS:
        sentence = sentence[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return sentence


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


def fetch_dpmes(period):
    """Organizations and policy areas with the scorecard of each."""
    organizations = dpmes_client.child_organizations(period) or []
    org_scorecards = {
        org["id"]: dpmes_client.organization_scorecard(org["id"], period) or {}
        for org in organizations
        if org.get("is_active", True)
    }
    policy_areas = dpmes_client.policy_area_scores(period) or []
    area_scorecards = {
        area["id"]: dpmes_client.policy_area_scorecard(area["id"], period) or {}
        for area in policy_areas
    }
    return organizations, org_scorecards, policy_areas, area_scorecards
