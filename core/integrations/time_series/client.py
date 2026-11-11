"""Calls to the time-series service."""

import os

import requests

DEFAULT_BASE_URL = "https://time-series.mopd.gov.et/api/mobile"
# Listing every topic with its indicators is slow; used by the AI catalog sync.
CATALOG_TIMEOUT = 60


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
