import requests

from AI.runtime.observability import increment, timed
from AI.runtime.resilience import retry_call
from dashboard import dpmes2
from mobile.api import dpmes_compat


def _get_json(url: str, *, params: dict | None, timeout: int, dependency_name: str, metric_prefix: str) -> dict:
    try:
        done = timed(f"{metric_prefix}_latency_ms")
        response = retry_call(
            lambda: requests.get(url, params=params, timeout=timeout),
            retries=2,
            on_exception=(requests.RequestException,),
            dependency_name=dependency_name,
        )
        done()
        if response.status_code == 200:
            increment(f"{metric_prefix}_success")
            return response.json()
        increment(f"{metric_prefix}_http_fail")
    except Exception:
        increment(f"{metric_prefix}_fail")
    return {}


def fetch_indicator_time_series(indicator_code: str, year=None, timeout=10):
    if not indicator_code:
        return {}

    return _get_json(
        "https://time-series.mopd.gov.et/api/mobile/annual_value/",
        params={"code": indicator_code, "year": year},
        timeout=timeout,
        dependency_name="time_series_api",
        metric_prefix="upstream_time_series",
    )


# DPMES replaced /api/ai/ministry-score and /api/ai/ministry-kpi-performance
# with the indicator-framework API. These keep the response shapes that
# AI.shared.upstream formats, so the tools and prompts are unchanged.

QUARTER_LABELS = {"3month": "Q1", "6month": "Q2", "9month": "Q3"}
# Ranges where a low score is the point of the question list worst first.
LOW_SCORE_BUCKETS = {"weak_performance", "no_data"}
MAX_PERFORMANCE_KPIS = 30


def _dpmes_period(year=None, quarter=None):
    """Year defaults to the last completed Ethiopian year, as on the dashboard.

    "12month" is the parser's default when a question names no quarter, so it
    means the annual score rather than Q4.
    """
    period = {"year": int(year) if year else dpmes2.current_ethiopian_year() - 1}
    if quarter in QUARTER_LABELS:
        period["quarter"] = dpmes_compat.QUARTER_TO_NUMBER[quarter]
    return period


def fetch_ministry_score(ministry_id: str, year=None, quarter=None, timeout=10):
    """`timeout` is kept for callers; the DPMES client applies its own."""
    if not ministry_id:
        return {}
    try:
        period = _dpmes_period(year, quarter)
        card = dpmes2.organization_scorecard(ministry_id, period) or {}
    except (dpmes2.DPMES2Error, KeyError, ValueError):
        increment("upstream_dpmes_score_fail")
        return {}

    increment("upstream_dpmes_score_success")
    score = card.get("score") or {}
    return {
        "responsible_ministry_eng": card.get("name"),
        "code": card.get("code"),
        "ministry_score_card": {
            "year": period["year"],
            "quarter": QUARTER_LABELS.get(quarter, "Annual"),
            "score": score.get("avg_score"),
            "score_color": score.get("color"),
        },
        "policy_areas": [
            {"policy_area_eng": area.get("name"), "score": (area.get("score") or {}).get("avg_score")}
            for area in card.get("policy_areas") or []
        ],
    }


def fetch_ministry_performance(ministry_id: str, year=None, quarter=None, performance_type=None, timeout=10):
    """KPIs in one performance bucket (or all of them), capped for the prompt.

    `timeout` is kept for callers; the DPMES client applies its own.
    """
    if not ministry_id:
        return {}
    try:
        period = _dpmes_period(year, quarter)
        card = dpmes2.organization_scorecard(ministry_id, period) or {}
        buckets = dpmes_compat.organization_performance(dpmes2.kpis_by_score_range(ministry_id, period))
    except (dpmes2.DPMES2Error, KeyError, ValueError):
        increment("upstream_dpmes_perf_fail")
        return {}

    increment("upstream_dpmes_perf_success")
    if performance_type in buckets:
        records = buckets[performance_type]
    else:
        records = [record for rows in buckets.values() for record in rows]
    records = sorted(
        records,
        key=lambda record: record.get("score") if record.get("score") is not None else -1,
        reverse=performance_type not in LOW_SCORE_BUCKETS,
    )[:MAX_PERFORMANCE_KPIS]

    label = QUARTER_LABELS.get(quarter, "Annual")
    return {
        "responsible_ministry_eng": card.get("name"),
        "code": card.get("code"),
        "kpis": [
            {"indicator_name": record.get("indicator_name"), "score": record.get("score"), "year": period["year"], "quarter": label}
            for record in records
        ],
    }
