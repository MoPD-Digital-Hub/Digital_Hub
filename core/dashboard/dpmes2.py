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
    return getattr(settings, "DPMES2_API_BASE", "https://dpmes.mopd.gov.et").rstrip("/")


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


def child_organizations(period=None):
    """All organizations under the API key's organization, with scores.

    Accepts a full period dict; a bare year is still allowed for callers that
    only care about the annual score.
    """
    if period is None:
        period = {"year": current_ethiopian_year()}
    elif not isinstance(period, dict):
        period = {"year": period}
    return get("/indicator-framework/api/organizations-score/", period)


def organization_scorecard(org_id, period):
    """Score, policy areas -> goals with scores, and KPI counts per score band."""
    return get(f"/indicator-framework/api/organizations/{org_id}/goals/", period)


def policy_area_scores(period=None):
    """Policy areas visible to the key's organization, each with its score."""
    period = period or {"year": current_ethiopian_year()}
    return get("/indicator-framework/api/policy-area-score/", period)


def policy_area_scorecard(policy_area_id, period):
    """A policy area's score, its goals with scores, and KPI counts per band."""
    return get(f"/indicator-framework/api/policy-areas/{policy_area_id}/goals/", period)


def key_organization_id():
    """ID of the organization the API key is scoped to (FDRE for a national key).

    Goal and KPI endpoints are organization-scoped, so this is the fallback
    when a caller does not name one.
    """
    def load():
        org = get("/indicator-framework/api/parent_organization_score/", {"year": current_ethiopian_year()})
        return org["id"]
    return _cached("key_organization_id", load)


def goal_kras(goal_id, org_id, period):
    """A goal's KRAs with scores, and each KRA's KPIs with their period records."""
    return get(f"/indicator-framework/api/goals/{goal_id}/kras/", {**period, "org": org_id})


def kpi_detail(kpi_id, org_id):
    """A KPI's definition and every record (yearly and quarterly) for an org.

    DPMES answers an unknown KPI with HTTP 200 and no data, which surfaces
    here as None.
    """
    return get(f"/indicator-framework/api/kpi_detail/{kpi_id}/{org_id}/")


def kpis_by_score_range(org_id, period):
    """Each score range with the organization's KPIs that scored inside it."""
    return get("/indicator-framework/api/kpis_by_score_range/", {**period, "org": org_id})


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
