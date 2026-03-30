import logging
import re

import certifi
import requests

from .config import get_retrieval_settings

LOGGER = logging.getLogger("AI.retrieval.ministry_score")

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
QUARTER_PATTERN = re.compile(r"\b(3month|6month|9month|12month)\b", re.IGNORECASE)
Q_ALIAS_PATTERN = re.compile(r"\bq([1-4])\b", re.IGNORECASE)

QUARTER_ALIASES = {
    "q1": "3month",
    "q2": "6month",
    "q3": "9month",
    "q4": "12month",
}

_public_body_catalog_cache = None


class MinistryScoreAPIError(Exception):
    pass


def parse_requested_period(question: str) -> tuple[int | None, str | None]:
    text = str(question or "").strip()
    if not text:
        return None, None

    year_match = YEAR_PATTERN.search(text)
    quarter_match = QUARTER_PATTERN.search(text)
    quarter_alias_match = Q_ALIAS_PATTERN.search(text)

    year = int(year_match.group(0)) if year_match else None
    if quarter_match:
        quarter = quarter_match.group(1).lower()
    elif quarter_alias_match:
        quarter = QUARTER_ALIASES.get(f"q{quarter_alias_match.group(1)}")
    else:
        quarter = None

    return year, quarter


def fetch_public_body_catalog(settings=None) -> list[dict]:
    global _public_body_catalog_cache
    if _public_body_catalog_cache is not None:
        return _public_body_catalog_cache

    settings = settings or get_retrieval_settings()
    url = f"{settings.dpmes_api_base.rstrip('/')}/api/digital-hub/all-ministries/"

    try:
        response = requests.get(
            url,
            timeout=settings.retrieval_timeout_seconds,
            verify=certifi.where(),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        LOGGER.warning("Public body catalog request failed: %s", str(exc))
        raise MinistryScoreAPIError(str(exc)) from exc
    except ValueError as exc:
        LOGGER.warning("Public body catalog returned invalid JSON.")
        raise MinistryScoreAPIError("Public body catalog returned invalid JSON.") from exc

    items = payload.get("data") if isinstance(payload, dict) else payload
    _public_body_catalog_cache = list(items or []) if isinstance(items, list) else []
    return _public_body_catalog_cache


def resolve_public_body_id(metadata: dict | None, settings=None) -> int | None:
    metadata = metadata or {}
    for key in ("ministry_id", "responsible_ministry_id", "public_body_id"):
        value = metadata.get(key)
        try:
            if value not in (None, ""):
                return int(value)
        except (TypeError, ValueError):
            continue

    ministry_name = str(
        metadata.get("responsible_ministry_eng")
        or metadata.get("responsible_ministry_amh")
        or metadata.get("public_body_name")
        or ""
    ).strip()
    ministry_code = str(metadata.get("code") or "").strip()
    if not ministry_name and not ministry_code:
        return None

    candidates = fetch_public_body_catalog(settings=settings)
    normalized_name = _normalize_label(ministry_name)
    normalized_code = _normalize_label(ministry_code)

    for item in candidates:
        if normalized_name and _normalize_label(item.get("responsible_ministry_eng")) == normalized_name:
            return _coerce_identifier(item.get("id"))
        if normalized_name and _normalize_label(item.get("responsible_ministry_amh")) == normalized_name:
            return _coerce_identifier(item.get("id"))
        if normalized_code and _normalize_label(item.get("code")) == normalized_code:
            return _coerce_identifier(item.get("id"))

    for item in candidates:
        item_name = _normalize_label(item.get("responsible_ministry_eng"))
        if normalized_name and normalized_name and (normalized_name in item_name or item_name in normalized_name):
            return _coerce_identifier(item.get("id"))

    return None


def fetch_public_body_score(public_body_id: int, *, year: int | None = None, quarter: str | None = None, settings=None) -> dict | None:
    if not public_body_id:
        return None

    settings = settings or get_retrieval_settings()
    url = f"{settings.dpmes_api_base.rstrip('/')}/api/ai/ministry-score/{public_body_id}"
    params = {}
    if year is not None:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter

    try:
        response = requests.get(
            url,
            params=params,
            timeout=settings.retrieval_timeout_seconds,
            verify=certifi.where(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except requests.RequestException as exc:
        LOGGER.warning("Public body score request failed for %s: %s", public_body_id, str(exc))
        raise MinistryScoreAPIError(str(exc)) from exc
    except ValueError as exc:
        LOGGER.warning("Public body score API returned invalid JSON for %s.", public_body_id)
        raise MinistryScoreAPIError("Public body score API returned invalid JSON.") from exc


def format_public_body_score_context(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""

    public_body = str(payload.get("responsible_ministry_eng") or "").strip()
    code = str(payload.get("code") or "").strip()
    count = payload.get("number_of_indicators")
    score_card = payload.get("ministry_score_card") or {}
    policy_areas = payload.get("policy_areas") or []

    parts = []
    if public_body:
        parts.append(f"public_body: {public_body}")
    if code:
        parts.append(f"public_body_code: {code}")
    if count not in (None, ""):
        parts.append(f"number_of_indicators: {count}")
    if score_card:
        score = str(score_card.get("score") or "").strip()
        year = score_card.get("year")
        quarter = str(score_card.get("quarter") or "").strip()
        if score:
            parts.append(f"ministry_score: {score}")
        if year not in (None, ""):
            parts.append(f"score_year: {year}")
        if quarter:
            parts.append(f"score_quarter: {quarter}")

    policy_area_lines = []
    for item in policy_areas:
        if not isinstance(item, dict):
            continue
        title = str(item.get("policy_area_eng") or "").strip()
        score = str(item.get("score") or "").strip()
        if title and score:
            policy_area_lines.append(f"- {title}: {score}")
        elif title:
            policy_area_lines.append(f"- {title}")
    if policy_area_lines:
        parts.append("policy_area_scores:\n" + "\n".join(policy_area_lines))

    return "\n".join(parts).strip()


def _normalize_label(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _coerce_identifier(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
