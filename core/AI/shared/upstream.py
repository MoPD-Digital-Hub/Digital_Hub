import requests

from AI.platform.observability import increment, timed
from AI.platform.resilience import retry_call


def fetch_indicator_time_series(indicator_code: str, year=None, timeout=10):
    if not indicator_code:
        return {}

    url = "https://time-series.mopd.gov.et/api/mobile/annual_value/"
    params = {"code": indicator_code, "year": year}
    try:
        done = timed("upstream_time_series_latency_ms")
        response = retry_call(
            lambda: requests.get(url, params=params, timeout=timeout),
            retries=2,
            on_exception=(requests.RequestException,),
            dependency_name="time_series_api",
        )
        done()
        if response.status_code == 200:
            increment("upstream_time_series_success")
            return response.json()
        increment("upstream_time_series_http_fail")
    except Exception:
        increment("upstream_time_series_fail")
    return {}


def fetch_ministry_score(ministry_id: str, year=None, quarter=None, timeout=10):
    if not ministry_id:
        return {}

    url = f"https://dpmes.mopd.gov.et/api/ai/ministry-score/{ministry_id}"
    params = {}
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter

    try:
        done = timed("upstream_dpmes_score_latency_ms")
        response = retry_call(
            lambda: requests.get(url, params=params, timeout=timeout),
            retries=2,
            on_exception=(requests.RequestException,),
            dependency_name="dpmes_score_api",
        )
        done()
        if response.status_code == 200:
            increment("upstream_dpmes_score_success")
            return response.json()
        increment("upstream_dpmes_score_http_fail")
    except Exception:
        increment("upstream_dpmes_score_fail")
    return {}


def fetch_ministry_performance(ministry_id: str, year=None, quarter=None, performance_type=None, timeout=10):
    if not ministry_id:
        return {}

    url = f"https://dpmes.mopd.gov.et/api/ai/ministry-kpi-performance/{ministry_id}"
    params = {}
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter
    if performance_type:
        params["performance_type"] = performance_type

    try:
        done = timed("upstream_dpmes_perf_latency_ms")
        response = retry_call(
            lambda: requests.get(url, params=params, timeout=timeout),
            retries=2,
            on_exception=(requests.RequestException,),
            dependency_name="dpmes_performance_api",
        )
        done()
        if response.status_code == 200:
            increment("upstream_dpmes_perf_success")
            return response.json()
        increment("upstream_dpmes_perf_http_fail")
    except Exception:
        increment("upstream_dpmes_perf_fail")
    return {}


def format_time_series_response(response, year):
    if not response:
        return "<p>Data not available</p>"

    ts = response.get("time_series")
    if not ts:
        value = response.get("value")
        if value is not None:
            label = year if year else "Requested period"
            return f"<p>{label}: {value}</p>"
        return "<p>Data not available</p>"

    output = ""
    for key, label in (("annual", "Annual Data"), ("quarter", "Quarterly Data"), ("month", "Monthly Data")):
        items = ts.get(key, [])
        if items:
            output += f"<h4>{label}</h4>"
            for item in items:
                output += f"<p>{item}</p>"
    return output or "<p>No historical data available</p>"


def format_ministry_score(data):
    if not data:
        return "<p>No ministry performance data found.</p>"

    score_card = data.get("ministry_score_card", {}) or {}
    rows = ""
    for area in data.get("policy_areas", []) or []:
        rows += f"<tr><td>{area.get('policy_area_eng', 'N/A')}</td><td>{area.get('score', 'N/A')}</td></tr>"

    return (
        f"<h3>Ministry Performance Overview: {data.get('responsible_ministry_eng', 'Unknown')} ({data.get('code', 'N/A')})</h3>"
        f"<p><b>Reporting Period:</b> {score_card.get('year', 'N/A')} - {score_card.get('quarter', 'Annual')}</p>"
        f"<p><b>Overall Ministry Score:</b> {score_card.get('score', 'N/A')}</p>"
        f"<p><b>Performance Status Color:</b>{score_card.get('score_color', "#000000")}</p>"
        f"<table><thead><tr><th>Policy Area</th><th>Score</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def format_ministry_performance(data):
    kpis = (data or {}).get("kpis", []) or []
    if not kpis:
        return "<p>No specific indicator performance data found for the selected criteria.</p>"

    rows = ""
    for item in kpis:
        rows += f"<tr><td>{item.get('indicator_name', 'Unknown Indicator')}</td><td>{item.get('score', 'N/A')}%</td></tr>"

    first = kpis[0]
    return (
        f"<h3>Indicator Performance List: {data.get('responsible_ministry_eng', 'Unknown')} ({data.get('code', 'N/A')})</h3>"
        f"<p><b>Reporting Period:</b> {first.get('year', 'N/A')} - {first.get('quarter', 'Annual')}</p>"
        f"<table><thead><tr><th>Indicator Name</th><th>Score</th></tr></thead><tbody>{rows}</tbody></table>"
    )
