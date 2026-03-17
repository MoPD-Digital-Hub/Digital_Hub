import json
import os
import re
from functools import lru_cache
from pathlib import Path
from .constants import DEFAULT_QUARTER, VALID_PERFORMANCE_KEYS, VALID_QUARTERS

_DEFAULTS_PATH = Path(__file__).with_name("rules.defaults.json")


def _normalize_terms(values) -> set[str]:
    return {
        re.sub(r"\s+", " ", str(value or "").strip().lower())
        for value in (values or [])
        if str(value or "").strip()
    }


def _normalize_quarter_patterns(pattern_map) -> list[tuple[re.Pattern[str], str]]:
    compiled = []
    for quarter, phrases in (pattern_map or {}).items():
        if quarter not in VALID_QUARTERS:
            continue
        normalized = [re.escape(term) for term in _normalize_terms(phrases)]
        if not normalized:
            continue
        compiled.append((re.compile(rf"\b({'|'.join(normalized)})\b", re.IGNORECASE), quarter))
    return compiled


def _load_json_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            return loaded if isinstance(loaded, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _merge_term_maps(base: dict, override: dict) -> dict:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if key not in VALID_PERFORMANCE_KEYS:
            continue
        merged[key] = list(value or [])
    return merged


@lru_cache(maxsize=1)
def _load_vocabulary_payload() -> dict:
    payload = _load_json_file(_DEFAULTS_PATH)
    override_path = os.getenv("AI_RULES_PATH", "").strip() or os.getenv("AI_VOCABULARY_PATH", "").strip()
    if not override_path:
        return payload

    override_payload = _load_json_file(Path(override_path))
    merged = dict(payload)
    if "time_series_terms" in override_payload:
        merged["time_series_terms"] = override_payload.get("time_series_terms") or []
    if "performance_terms" in override_payload:
        merged["performance_terms"] = _merge_term_maps(
            payload.get("performance_terms") or {},
            override_payload.get("performance_terms") or {},
        )
    if "quarter_patterns" in override_payload:
        merged["quarter_patterns"] = override_payload.get("quarter_patterns") or {}
    return merged


_VOCABULARY = _load_vocabulary_payload()

TIME_SERIES_TERMS = _normalize_terms(_VOCABULARY.get("time_series_terms"))

_PERFORMANCE_TERMS = {
    key: _normalize_terms((_VOCABULARY.get("performance_terms") or {}).get(key))
    for key in VALID_PERFORMANCE_KEYS
}

PERFORMANCE_ON_TRACK_TERMS = _PERFORMANCE_TERMS["on_track"]
PERFORMANCE_IN_PROGRESS_TERMS = _PERFORMANCE_TERMS["in_progress"]
PERFORMANCE_WEAK_TERMS = _PERFORMANCE_TERMS["weak_performance"]
PERFORMANCE_NO_DATA_TERMS = _PERFORMANCE_TERMS["no_data"]

QUARTER_PATTERNS = _normalize_quarter_patterns(_VOCABULARY.get("quarter_patterns"))


def contains_time_series_vocabulary(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return any(term in normalized for term in TIME_SERIES_TERMS)


def match_performance_vocabulary(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    for key in ("no_data", "weak_performance", "on_track", "in_progress"):
        if any(term in normalized for term in _PERFORMANCE_TERMS.get(key, set())):
            return key
    return None
