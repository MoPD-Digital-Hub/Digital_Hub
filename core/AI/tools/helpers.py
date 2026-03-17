import re
from typing import Any

from django.conf import settings

from AI.parsing import extract_performance_type, extract_year_quarter


def normalize_quarter(value: Any) -> str | None:
    quarter = str(value or "").strip().lower()
    if quarter in {"3month", "6month", "9month", "12month"}:
        return quarter
    return None


def normalize_year(value: Any) -> str | None:
    year = str(value or "").strip()
    if re.fullmatch(r"(19|20)\d{2}", year):
        return year
    return None


def max_docs() -> int:
    return max(1, getattr(settings, "AI_MAX_RETRIEVAL_DOCS", 4))


def resolve_period(question: str, arguments: dict | None = None) -> dict:
    period = extract_year_quarter(None, question)
    args = arguments or {}
    period["year"] = normalize_year(args.get("year")) or period.get("year")
    period["quarter"] = normalize_quarter(args.get("quarter")) or period.get("quarter")
    return period


def resolve_performance_type(question: str, arguments: dict | None = None) -> str | None:
    args = arguments or {}
    return args.get("performance_type") or extract_performance_type(None, question)
