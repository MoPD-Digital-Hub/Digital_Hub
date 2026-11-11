"""Fetch the indicator and organization lists the catalog is built from."""

import re

from integrations.dpmes import client as dpmes_client

# Long technical descriptions drown out the indicator name in the embedding,
# so the catalog keeps only their opening.
MAX_DESCRIPTION_CHARS = 220


def lead_sentence(text):
    """The first sentence, capped, so a description supports the name instead of dominating it."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if len(sentence) > MAX_DESCRIPTION_CHARS:
        sentence = sentence[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return sentence


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
