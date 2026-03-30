import logging

import certifi
import requests

from .config import get_retrieval_settings

LOGGER = logging.getLogger("AI.retrieval.time_series")


class TimeSeriesAPIError(Exception):
    pass


def fetch_indicator_time_series(indicator_code: str):
    code = str(indicator_code or "").strip()
    if not code:
        return None

    settings = get_retrieval_settings()
    base_url = settings.time_series_api_base.rstrip("/")
    url = f"{base_url}/annual_value/"

    try:
        response = requests.get(
            url,
            params={"code": code},
            timeout=settings.retrieval_timeout_seconds,
            verify=certifi.where(),
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        LOGGER.warning("Time-series API request failed for %s: %s", code, str(exc))
        raise TimeSeriesAPIError(str(exc)) from exc


def format_time_series_context(payload: dict | None, *, limit: int = 6) -> str:
    if not isinstance(payload, dict):
        return ""

    indicator = str(payload.get("indicator") or "").strip()
    series = payload.get("time_series") or {}
    annual = _format_entries(series.get("annual"), ("year", "value"), limit=limit)
    quarter = _format_entries(series.get("quarter"), ("year", "quarter", "value"), limit=limit)
    month = _format_entries(series.get("month"), ("year", "month", "value"), limit=limit)

    parts = []
    if indicator:
        parts.append(f"indicator: {indicator}")
    if annual:
        parts.append("annual_values:\n" + annual)
    if quarter:
        parts.append("quarter_values:\n" + quarter)
    if month:
        parts.append("month_values:\n" + month)
    return "\n".join(parts).strip()


def build_time_series_chart(payload: dict | None, metadata: dict | None = None) -> dict:
    if not isinstance(payload, dict):
        return {}

    metadata = metadata or {}
    series = payload.get("time_series") or {}
    annual = _chart_points(series.get("annual"), "year")
    quarter = _chart_points(series.get("quarter"), "quarter")
    month = _chart_points(series.get("month"), "month")

    chart_type = "line"
    labels = []
    data = []

    if annual["labels"]:
        labels = annual["labels"]
        data = annual["data"]
    elif quarter["labels"]:
        labels = quarter["labels"]
        data = quarter["data"]
    elif month["labels"]:
        labels = month["labels"]
        data = month["data"]
    else:
        return {}

    label = _chart_label(payload, metadata)
    return {
        "type": chart_type,
        "label": label,
        "labels": labels,
        "data": data,
        "indicator_code": str((metadata or {}).get("indicator_code") or payload.get("indicator") or "").strip(),
    }


def _format_entries(entries, fields, *, limit: int):
    rows = []
    for item in list(entries or [])[:limit]:
        if not isinstance(item, dict):
            continue
        values = []
        for field in fields:
            value = item.get(field)
            if value in (None, ""):
                continue
            values.append(f"{field}={value}")
        if values:
            rows.append("- " + ", ".join(values))
    return "\n".join(rows)


def _chart_points(entries, time_key: str) -> dict:
    labels = []
    data = []
    for item in list(entries or []):
        if not isinstance(item, dict):
            continue
        value = _to_number(item.get("value"))
        if value is None:
            continue
        if time_key == "year":
            label = str(item.get("year") or "").strip()
        elif time_key == "quarter":
            year = str(item.get("year") or "").strip()
            quarter = str(item.get("quarter") or "").strip()
            label = " ".join(part for part in (year, quarter) if part)
        else:
            year = str(item.get("year") or "").strip()
            month = str(item.get("month") or "").strip()
            label = " ".join(part for part in (year, month) if part)
        if not label:
            continue
        labels.append(label)
        data.append(value)
    return {"labels": labels, "data": data}


def _chart_label(payload: dict, metadata: dict) -> str:
    indicator = str(
        metadata.get("indicator_eng")
        or metadata.get("indicator")
        or payload.get("indicator")
        or metadata.get("indicator_code")
        or "Indicator"
    ).strip()
    unit = str(
        metadata.get("unit_eng")
        or metadata.get("unit")
        or metadata.get("measurement_unit")
        or metadata.get("unit_name")
        or ""
    ).strip()
    return f"{indicator} ({unit})" if unit else indicator


def _to_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 2)
