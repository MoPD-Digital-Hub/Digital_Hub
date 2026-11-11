"""Ethiopia's national SDG platform (sdg.mopd.gov.et): goals, targets and indicator data.

The platform is a Next.js site without a public JSON API. Each goal page embeds
its data (the 17 goals, and the goal's targets and indicators with their series)
in a __NEXT_DATA__ script. Reading the page, rather than /_next/data/<build id>/,
keeps working when the site is redeployed under a new build id.
"""

import json
import os
import re

import requests
from django.core.cache import cache

GOAL_IDS = tuple(range(1, 18))
SOURCE_NAME = "Ethiopia's national SDG platform"
SOURCE_SITE = "sdg.mopd.gov.et"
CACHE_SECONDS = 3600
TIMEOUT_SECONDS = 30
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


class SDGError(Exception):
    """The platform could not be reached or its page could not be read."""


def base_url():
    return os.getenv("SDG_PLATFORM_BASE", "https://sdg.mopd.gov.et").rstrip("/")


def goal_url(goal_id):
    return f"{base_url()}/goals/sdg/{int(goal_id)}/"


def _page_props(goal_id):
    key = f"sdg-platform:goal:{int(goal_id)}"
    props = cache.get(key)
    if props is not None:
        return props
    try:
        response = requests.get(goal_url(goal_id), headers={"User-Agent": "DigitalHub/1.0"}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SDGError(f"the SDG platform is unreachable ({exc})") from exc
    match = NEXT_DATA.search(response.text)
    if not match:
        raise SDGError("the SDG platform page has no embedded data")
    try:
        props = json.loads(match.group(1))["props"]["pageProps"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SDGError("the SDG platform page data could not be read") from exc
    cache.set(key, props, CACHE_SECONDS)
    return props


def goal(goal_id):
    """One goal with its targets and indicators, and the list of all 17 goals.

    {"countryName", "country", "framework", "goal", "goals", "targets", "indicators"};
    "goal" is None when the platform does not list the id.
    """
    props = _page_props(goal_id)
    sdg = (props.get("data") or {}).get("sdg") or {}
    gid = str(int(goal_id))
    return {
        "countryName": props.get("countryName") or "Ethiopia",
        "country": props.get("country") or "ethiopia",
        "framework": props.get("framework") or "sdg",
        "goal": next((g for g in sdg.get("goals") or [] if str(g.get("id")) == gid), None),
        "goals": list(sdg.get("goals") or []),
        "targets": [t for t in sdg.get("targets") or [] if str(t.get("goal")) == gid],
        "indicators": [i for i in sdg.get("indicators") or [] if str(i.get("goal")) == gid],
    }
