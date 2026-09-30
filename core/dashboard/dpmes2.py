"""Thin client for the DPMES2 organization-performance API.

Authenticates with the X-API-Key issued to the Digital Hub (settings
DPMES2_API_KEY). Performance endpoints require an Ethiopian calendar
`year`; the current one is read from DPMES2's public server-date endpoint
and cached, so callers may omit it.
"""

import threading
import time

import requests
from django.conf import settings


class DPMES2Error(Exception):
    pass


_cache_lock = threading.Lock()
_cache = {}
CACHE_TTL_SECONDS = 3600


def _cached(key, loader):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.time() + CACHE_TTL_SECONDS, value)
    return value


def base_url():
    return getattr(settings, "DPMES2_API_BASE", "https://dpmes2.mopd.gov.et").rstrip("/")


def is_configured():
    return bool(getattr(settings, "DPMES2_API_KEY", ""))


def get(path, params=None, timeout=15):
    """GET a DPMES2 endpoint and return the unwrapped `data` payload."""
    headers = {}
    if is_configured():
        headers["X-API-Key"] = settings.DPMES2_API_KEY
    try:
        response = requests.get(f"{base_url()}{path}", params=params or {}, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise DPMES2Error(f"Failed to reach DPMES2: {exc}") from exc

    if response.status_code in (401, 403):
        raise DPMES2Error("DPMES2 rejected the API key (check DPMES2_API_KEY).")
    if response.status_code >= 400:
        raise DPMES2Error(f"DPMES2 returned HTTP {response.status_code} for {path}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise DPMES2Error("DPMES2 returned a non-JSON response.") from exc
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def server_date():
    return _cached("server_date", lambda: get("/indicator-framework/api/server-date/"))


def current_ethiopian_year():
    return int(str(server_date()["ethio_date"]).split("-")[0])


def score_ranges():
    return _cached("score_ranges", lambda: get("/indicator-framework/api/score_range/"))


def child_organizations(year=None):
    """All organizations under the API key's organization, with scores."""
    year = year or current_ethiopian_year()
    return get("/indicator-framework/api/organizations-score/", {"year": year})


def organization_scorecard(org_id, period):
    """Score, policy areas -> goals with scores, and KPI counts per score band."""
    return get(f"/indicator-framework/api/organizations/{org_id}/goals/", period)


def period_from_query(query_params):
    """Build the year/quarter/month/plan filter DPMES2 expects. `year`
    defaults to the current Ethiopian year; the others pass through."""
    period = {}
    for key in ("year", "quarter", "month", "plan"):
        value = query_params.get(key)
        if value not in (None, ""):
            period[key] = value
    if "year" not in period:
        period["year"] = current_ethiopian_year()
    return period
