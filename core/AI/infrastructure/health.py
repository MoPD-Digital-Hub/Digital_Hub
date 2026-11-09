import requests

from AI.infrastructure.providers import get_llm_instance, get_remote_embeddings
from AI.infrastructure.vectorstore import ensure_collection
from dashboard import dpmes2


def _http_up(url: str, timeout: float = 2.5) -> bool:
    if not url:
        return False
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False


def check_llm():
    return get_llm_instance() is not None


def check_embeddings():
    return get_remote_embeddings() is not None


def check_milvus():
    return ensure_collection() is not None


def check_time_series_api():
    return _http_up("https://time-series.mopd.gov.et/api/mobile/annual_value/?code=EG-GDPCP-01")


def _dpmes_answers(path, params=None):
    """True when DPMES accepts the API key and answers; a refusal is a failure."""
    try:
        return dpmes2.get(path, params) is not None
    except dpmes2.DPMES2Error:
        return False


def check_dpmes_score_api():
    return _dpmes_answers("/indicator-framework/api/score_range/")


def check_dpmes_performance_api():
    try:
        year = dpmes2.current_ethiopian_year()
    except (dpmes2.DPMES2Error, KeyError, ValueError):
        return False
    return _dpmes_answers("/indicator-framework/api/kpis_by_score_range/", {"year": year})


DEPENDENCY_CHECKS = {
    "llm": check_llm,
    "embeddings": check_embeddings,
    "milvus": check_milvus,
    "time_series_api": check_time_series_api,
    "dpmes_score_api": check_dpmes_score_api,
    "dpmes_performance_api": check_dpmes_performance_api,
}


def run_dependency_checks(names=None):
    selected = names or list(DEPENDENCY_CHECKS.keys())
    results = {}
    for name in selected:
        checker = DEPENDENCY_CHECKS.get(name)
        if checker is None:
            results[name] = {"ok": False, "error": "UNKNOWN_DEPENDENCY"}
            continue
        try:
            results[name] = {"ok": bool(checker())}
        except Exception as exc:
            results[name] = {"ok": False, "error": str(exc)}
    return results
