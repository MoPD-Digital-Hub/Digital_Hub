"""Scores and values from the other services, in one plain shape.

DPMES scores organizations, policy areas and KPIs per Ethiopian-calendar
period; the time-series service holds indicator values. Everything here is
read through the cache: scores only change when a new period is reported, so a
dashboard costs no upstream calls most of the time.

Ids are strings throughout, because a followed item stores its id as text.
"""

from django.core.cache import cache

from integrations.dpmes import client as dpmes_client
from integrations.time_series import client as time_series_client

CACHE_SECONDS = 6 * 3600
# Points kept from an indicator's series (enough for a trend line).
SERIES_POINTS = 12
_MISSING = object()


class SourceError(Exception):
    """A service could not be read. `code` is safe to show; the text has the detail."""

    def __init__(self, message, code="UPSTREAM_ERROR"):
        super().__init__(message)
        self.code = code


def cached(key, loader, seconds=CACHE_SECONDS):
    key = f"preferences:{key}"
    value = cache.get(key, _MISSING)
    if value is _MISSING:
        value = loader()
        cache.set(key, value, seconds)
    return value


def number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _dpmes(call, *args):
    if not dpmes_client.is_configured():
        raise SourceError("DPMES2_API_KEY is not set.", code="DPMES2_NOT_CONFIGURED")
    try:
        return call(*args)
    except dpmes_client.DPMES2Error as exc:
        raise SourceError(str(exc)) from exc


def _time_series(call, *args):
    try:
        return call(*args)
    except time_series_client.TimeSeriesError as exc:
        raise SourceError(str(exc)) from exc


def direction(value):
    """'increasing' when a higher value is better, 'decreasing' when lower is, else ''."""
    text = str(value or "").strip().lower()
    if text.startswith("inc"):
        return "increasing"
    if text.startswith("dec"):
        return "decreasing"
    return ""


# --- Periods ----------------------------------------------------------------


def period_key(period):
    return f"{period['year']}-{period['quarter']}" if period.get("quarter") else str(period["year"])


def period_label(period):
    return f"{period['year']} Q{period['quarter']}" if period.get("quarter") else str(period["year"])


def previous_period(period):
    if not period.get("quarter"):
        return {"year": period["year"] - 1}
    if period["quarter"] > 1:
        return {"year": period["year"], "quarter": period["quarter"] - 1}
    return {"year": period["year"] - 1, "quarter": 4}


def current_year():
    try:
        return _dpmes(dpmes_client.current_ethiopian_year)
    except (KeyError, ValueError, TypeError) as exc:
        raise SourceError(f"DPMES returned an unreadable date: {exc}") from exc


def latest_scored_quarter():
    """The newest quarter in which any organization has a score.

    The current quarter is usually not reported yet, so step back from the end
    of the current year until scores appear.
    """
    def find():
        year = current_year()
        for candidate_year in (year, year - 1, year - 2):
            for quarter in (4, 3, 2, 1):
                period = {"year": candidate_year, "quarter": quarter}
                if any(has_score(row) for row in organizations(period)):
                    return period
        return {"year": year - 1, "quarter": 4}

    return cached("latest_quarter", find)


def periods(kind):
    """(current, previous) for 'quarter' or 'year'.

    A year is compared once it is complete, so 'year' is last year against the
    one before; 'quarter' is the newest reported quarter against the one before.
    """
    current = latest_scored_quarter() if kind == "quarter" else {"year": current_year() - 1}
    return current, previous_period(current)


def describe_periods(kind, current, previous):
    return {
        "type": kind,
        "current": {**current, "label": period_label(current)},
        "previous": {**previous, "label": period_label(previous)},
    }


# --- DPMES ------------------------------------------------------------------


def has_score(row):
    """An organization or policy area with nothing reported scores exactly 0,
    which cannot be told apart from 'no data'; neither is compared."""
    return row.get("score") is not None and row["score"] > 0


def _scored(row):
    score = row.get("score") if isinstance(row.get("score"), dict) else {}
    return {
        "id": str(row.get("id")),
        "name": (row.get("name") or row.get("trans_name") or "").strip(),
        "name_am": (row.get("name_eth") or "").strip(),
        "code": (row.get("code") or "").strip(),
        "icon": row.get("icon") or "",
        "score": number(score.get("avg_score")),
        "color": score.get("color") or "",
    }


def organizations(period):
    """Every organization under the Digital Hub's key, with its score for `period`."""
    return cached(
        f"organizations:{period_key(period)}",
        lambda: [_scored(row) for row in _dpmes(dpmes_client.child_organizations, period) or []],
    )


def policy_areas(period):
    return cached(
        f"policy_areas:{period_key(period)}",
        lambda: [_scored(row) for row in _dpmes(dpmes_client.policy_area_scores, period) or []],
    )


def _kpi(row, organization_id):
    record = (row.get("records") or [{}])[0]
    score, performance = number(record.get("score")), number(record.get("performance"))
    return {
        "id": str(row.get("id")),
        "organization_id": str(organization_id),
        "name": (row.get("name") or row.get("trans_name") or "").strip(),
        "name_am": (row.get("name_eth") or "").strip(),
        "code": (row.get("code") or "").strip(),
        "category": (row.get("for_category") or "").strip(),
        "unit": (row.get("measurement_units") or "").strip(),
        "direction": direction(row.get("kpi_characteristics")),
        "target": number(record.get("target")),
        "performance": performance,
        "score": score,
        "color": record.get("score_color") or "",
        "has_data": performance is not None and score is not None and score >= 0,
    }


def organization_kpis(organization_id, period):
    """An organization's KPIs with their target, result and score for `period`."""
    def load():
        bands = _dpmes(dpmes_client.kpis_by_score_range, organization_id, period) or []
        return [_kpi(row, organization_id) for band in bands for row in band.get("kpis") or []]

    return cached(f"kpis:{organization_id}:{period_key(period)}", load)


def _record_period(record):
    """('2018 Q2', sort key) from a record's ethio_date ('2018-02' or '2018')."""
    year, _, quarter = str(record.get("ethio_date") or "").partition("-")
    if record.get("record_type") == "quarterly" and quarter.isdigit():
        return f"{year} Q{int(quarter)}", (year, quarter)
    return year, (year, "99")


def kpi(kpi_id, organization_id):
    """A KPI's definition and its full history for one organization; None when unknown."""
    def load():
        row = _dpmes(dpmes_client.kpi_detail, kpi_id, organization_id)
        if not row:
            return None
        history = []
        for record in row.get("records") or []:
            label, order = _record_period(record)
            history.append({
                "period": label,
                "type": "quarter" if record.get("record_type") == "quarterly" else "year",
                "target": number(record.get("target")),
                "performance": number(record.get("performance")),
                "score": number(record.get("score")),
                "_order": order,
            })
        history.sort(key=lambda point: point["_order"])
        for point in history:
            del point["_order"]
        summary = _kpi({**row, "records": []}, organization_id)
        return {key: summary[key] for key in ("id", "organization_id", "name", "name_am", "code", "category",
                                              "unit", "direction")} | {"history": history}

    return cached(f"kpi:{kpi_id}:{organization_id}", load)


def score_bands():
    """Score ranges from lowest to highest, without the 'No Data' range."""
    def load():
        bands = []
        for row in _dpmes(dpmes_client.score_ranges) or []:
            if row.get("is_default"):
                continue
            bands.append({
                "name": row.get("name_en") or row.get("trans_name") or "",
                "name_am": row.get("name_eth") or "",
                "start": number(row.get("start")),
                "end": number(row.get("end")),
                "color": row.get("color") or "",
            })
        return sorted((band for band in bands if band["start"] is not None), key=lambda band: band["start"])

    return cached("score_bands", load)


def band_for(score, bands):
    """The band a score falls in: the highest one that starts at or below it."""
    if score is None or score < 0:
        return None
    match = None
    for band in bands:
        if score >= band["start"]:
            match = band
    return match


# --- Time series ------------------------------------------------------------


def _point_label(point):
    label = str(point.get("for_datapoint") or "")
    for key in ("for_quarter", "for_month", "for_week", "for_day"):
        if point.get(key) not in (None, ""):
            label += f" {point[key]}"
    return label.strip()


def _series(row):
    """(frequency, points) of the series the service marks as the latest one."""
    names = [str(row.get("latest_data") or ""), "month", "quarter", "annual"]
    for name in names:
        points = row.get(f"{name}_data") if name else None
        values = [
            {"period": _point_label(point), "value": number(point.get("performance"))}
            for point in points or [] if number(point.get("performance")) is not None
        ]
        if values:
            return name, values[-SERIES_POINTS:]
    return "", []


def indicator(indicator_id):
    """A time-series indicator with its recent values; None when unknown."""
    def load():
        row = _time_series(time_series_client.indicator_detail, indicator_id)
        if not row:
            return None
        frequency, series = _series(row)
        return {
            "id": str(row.get("id")),
            "name": (row.get("title_ENG") or "").strip(),
            "name_am": (row.get("title_AMH") or "").strip(),
            "code": (row.get("code") or "").strip(),
            "unit": (row.get("measurement_units") or "").strip(),
            "direction": direction(row.get("kpi_characteristics")),
            "frequency": frequency,
            "series": series,
        }

    return cached(f"indicator:{indicator_id}", load, seconds=3600)


def search_indicators(query):
    """Indicators matching `query`, each with the category it belongs to."""
    results, seen = [], set()
    for category in _time_series(time_series_client.search, query) or []:
        for row in category.get("indicators") or []:
            identifier = str(row.get("id"))
            if identifier in seen or not row.get("id"):
                continue
            seen.add(identifier)
            results.append({
                "id": identifier,
                "name": (row.get("title_ENG") or "").strip(),
                "name_am": (row.get("title_AMH") or "").strip(),
                "code": (row.get("code") or "").strip(),
                "category": (category.get("name_ENG") or "").strip(),
            })
    return results
