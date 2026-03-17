import requests

from AI.runtime.observability import increment, timed
from AI.runtime.resilience import retry_call


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


def fetch_ministry_score(ministry_id: str, year=None, quarter=None, timeout=10):
    if not ministry_id:
        return {}

    params = {}
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter

    return _get_json(
        f"https://dpmes.mopd.gov.et/api/ai/ministry-score/{ministry_id}",
        params=params,
        timeout=timeout,
        dependency_name="dpmes_score_api",
        metric_prefix="upstream_dpmes_score",
    )


def fetch_ministry_performance(ministry_id: str, year=None, quarter=None, performance_type=None, timeout=10):
    if not ministry_id:
        return {}

    params = {}
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter
    if performance_type:
        params["performance_type"] = performance_type

    return _get_json(
        f"https://dpmes.mopd.gov.et/api/ai/ministry-kpi-performance/{ministry_id}",
        params=params,
        timeout=timeout,
        dependency_name="dpmes_performance_api",
        metric_prefix="upstream_dpmes_perf",
    )
