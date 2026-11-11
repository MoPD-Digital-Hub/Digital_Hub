"""Calls to the time-series service."""

import os

import requests

DEFAULT_BASE_URL = "https://time-series.mopd.gov.et/api/mobile"
# Listing every topic with its indicators is slow; used by the AI catalog sync.
CATALOG_TIMEOUT = 60


class TimeSeriesError(Exception):
    pass


def base_url():
    """The service's mobile API root, from TIME_SERIES_API_BASE."""
    return os.getenv("TIME_SERIES_API_BASE", DEFAULT_BASE_URL).rstrip("/")


def fetch_topics(session=None):
    """Every topic with its categories and (nested) indicators."""
    session = session or requests.Session()
    base = base_url()
    response = session.get(f"{base}/topic-list/", timeout=CATALOG_TIMEOUT)
    response.raise_for_status()
    topics = []
    for topic in response.json().get("data") or []:
        detail = session.get(f"{base}/topic-detail/{topic['id']}/", timeout=CATALOG_TIMEOUT)
        detail.raise_for_status()
        topics.append(detail.json().get("data") or {})
    return topics


def annual_value(code, timeout=20):
    """The raw response for one indicator's series, looked up by code."""
    return requests.get(f"{base_url()}/annual_value/", params={"code": code}, timeout=timeout)


def get_json(path, params=None, timeout=20):
    """GET a time-series endpoint and return its `data`. None when the service
    answers 404 (an unknown indicator); TimeSeriesError for any other failure."""
    try:
        response = requests.get(f"{base_url()}{path}", params=params or {}, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise TimeSeriesError(f"Failed to reach the time-series service: {exc}") from exc
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise TimeSeriesError(f"The time-series service returned HTTP {response.status_code} for {path}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise TimeSeriesError("The time-series service returned a non-JSON response.") from exc
    return payload.get("data") if isinstance(payload, dict) else payload


def indicator_detail(indicator_id):
    """One indicator with its annual, quarterly and monthly series; None when unknown."""
    return get_json(f"/indicator-detail/{indicator_id}/")


def search(query):
    """Categories whose indicators match `query`, each with those indicators."""
    return get_json("/general_search/", {"q": query}) or []
