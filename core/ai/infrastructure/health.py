import requests

from ai.engine import llm
from ai.engine.sources import time_series_base_url
from integrations.dpmes import client as dpmes_client


def _http_up(url: str, timeout: float = 2.5) -> bool:
    if not url:
        return False
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False


def _gateway_answers(config):
    """True when the gateway accepts the key and lists its models."""
    try:
        response = requests.get(f"{config['base_url']}/models", timeout=5,
                                headers={"Authorization": f"Bearer {config['api_key']}"})
        return response.status_code == 200
    except Exception:
        return False


def check_llm():
    return _gateway_answers(llm.chat_config())


def check_embeddings():
    return _gateway_answers(llm.embedding_config())


def check_time_series_api():
    return _http_up(f"{time_series_base_url()}/annual_value/?code=EG-GDPCP-01")


def _dpmes_answers(path, params=None):
    """True when DPMES accepts the API key and answers; a refusal is a failure."""
    try:
        return dpmes_client.get(path, params) is not None
    except dpmes_client.DPMES2Error:
        return False


def check_dpmes_score_api():
    return _dpmes_answers("/indicator-framework/api/score_range/")


def check_dpmes_performance_api():
    try:
        year = dpmes_client.current_ethiopian_year()
    except (dpmes_client.DPMES2Error, KeyError, ValueError):
        return False
    return _dpmes_answers("/indicator-framework/api/kpis_by_score_range/", {"year": year})


DEPENDENCY_CHECKS = {
    "llm": check_llm,
    "embeddings": check_embeddings,
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
