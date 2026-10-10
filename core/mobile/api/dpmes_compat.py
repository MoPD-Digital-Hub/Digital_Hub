"""Adapters between the DPMES API and the response shape our clients expect.

DPMES replaced the `/api/digital-hub/` endpoints (now 404) with the
indicator-framework API documented at https://dpmes.mopd.gov.et/api/docs/.
The new endpoints carry the same information under different field names and
take `quarter` as 1-4 instead of the legacy `3month`/`6month`/... strings.

The dashboard scorecard components and the mobile app were both written
against the old shape, so we translate here instead of changing every client.
Keep these mappings in step with the components in
static/assets/js/components/{policy-area,public-body}-scorecard.js.
"""

from dashboard import dpmes2

# Legacy clients send quarter as a cumulative-month label; DPMES wants 1-4.
QUARTER_TO_NUMBER = {
    "3month": 1,
    "6month": 2,
    "9month": 3,
    "12month": 4,
}
NUMBER_TO_QUARTER = {number: label for label, number in QUARTER_TO_NUMBER.items()}


def build_period(query_params):
    """Translate incoming query params into the period DPMES expects.

    `year` defaults to the current Ethiopian year. `quarter` accepts either
    the legacy label or a plain number. `month` and `plan` pass through.
    """
    period = {}

    year = query_params.get("year")
    period["year"] = year if year not in (None, "") else dpmes2.current_ethiopian_year()

    quarter = query_params.get("quarter")
    if quarter not in (None, ""):
        if quarter in QUARTER_TO_NUMBER:
            period["quarter"] = QUARTER_TO_NUMBER[quarter]
        elif str(quarter).isdigit():
            period["quarter"] = int(quarter)

    for key in ("month", "plan"):
        value = query_params.get(key)
        if value not in (None, ""):
            period[key] = value

    return period


def _score(item):
    score = item.get("score") or {}
    return {
        "avg_score": score.get("avg_score"),
        "scorecard_color": score.get("color"),
        "total_weight": score.get("total_weight"),
    }


def policy_area(item, rank):
    """DPMES policy-area-score row -> legacy policy area shape."""
    name = item.get("name") or item.get("trans_name") or ""
    return {
        "id": item.get("id"),
        "policyAreaEng": name,
        "policyAreaAmh": item.get("name_eth") or name,
        "policyAreaCode": item.get("code"),
        "code": item.get("code"),
        "image_icon": item.get("icon"),
        "bg_image": item.get("background_image"),
        "policy_area_score_card": _score(item),
        "rank": rank,
        # The new API has no per-client visibility flag; everything the key can
        # see is publishable, and the dashboard passes show-all anyway.
        "show_mobile_dashboard": True,
        "level": item.get("level"),
        "parent": item.get("parent"),
        "plan": item.get("plan"),
    }


def ministry(item, rank):
    """DPMES organizations-score row -> legacy ministry/public body shape."""
    name = item.get("name") or item.get("trans_name") or ""
    return {
        "id": item.get("id"),
        "responsible_ministry_eng": name,
        "responsible_ministry_amh": item.get("name_eth") or name,
        "code": item.get("code"),
        "image": item.get("icon"),
        "ministry_score_card": _score(item),
        "ministry_is_visable": bool(item.get("is_active", True)),
        "show_mobile_dashboard": True,
        "ministry_rank": item.get("order") or rank,
        # organizations-score carries no per-organization indicator count, so
        # clients render the label only when this is not None.
        "count_indicator": None,
        "parent": item.get("parent"),
    }


def map_rows(rows, mapper):
    if not isinstance(rows, list):
        return []
    return [mapper(row, index + 1) for index, row in enumerate(rows) if isinstance(row, dict)]


def quarter_for_ethiopian_month(month):
    """Ethiopian months 1-3 -> Q1 ... 10-13 -> Q4 (Pagume rolls into Q4)."""
    return NUMBER_TO_QUARTER[min(4, (int(month) - 1) // 3 + 1)]


# --- Detail pages --------------------------------------------------------
#
# The detail endpoints are organization-scoped in the new API: goal KRAs and
# KPI records need an `org`. Callers pass one when the page knows it and fall
# back to the API key's own organization (the national view) otherwise.


def _name(item):
    return item.get("name") or item.get("trans_name") or ""


def goal(item, org_id=None):
    """DPMES goal row -> legacy goal shape used by both detail pages.

    `responsible_ministries` is the owning organization's id when known. The
    public-body page links goals with it; the policy-area endpoint does not say
    which organization owns a goal, so it is None there.
    """
    name = _name(item)
    score = _score(item)
    return {
        "id": item.get("id"),
        "goal_name_eng": name,
        "goal_name_amh": item.get("name_eth") or name,
        "code": item.get("code"),
        "goal_score_card": score,
        "ministry_strategic_goal_score_card": score,
        "goal_is_visable": True,
        "responsible_ministries": org_id,
    }


def policy_area_detail(data):
    """policy-areas/{id}/goals/ -> legacy policy-area-detail payload."""
    detail = policy_area(data, rank=None)
    detail["policy_area_goal"] = [goal(row) for row in data.get("goals") or [] if isinstance(row, dict)]
    detail["performance_analysis"] = data.get("performance_analysis") or {}
    return detail


def organization_policy_areas(data):
    """organizations/{id}/goals/ -> legacy ministry-detail list of policy areas."""
    org_id = data.get("id")
    areas = []
    for area in data.get("policy_areas") or []:
        if not isinstance(area, dict):
            continue
        name = _name(area)
        score = _score(area)
        areas.append({
            "id": area.get("id"),
            "policyAreaEng": name,
            "policyAreaAmh": area.get("name_eth") or name,
            "code": area.get("code"),
            "image_icon": area.get("icon"),
            "bg_image": area.get("background_image"),
            "ministry_policy_area_score_card": score,
            "policy_area_score_card": score,
            "policy_area_goal": [goal(row, org_id) for row in area.get("goals") or [] if isinstance(row, dict)],
        })
    return areas


def find_goal_score(scorecard, goal_id):
    """The authoritative score for a goal from an organization scorecard."""
    for area in (scorecard or {}).get("policy_areas") or []:
        for row in area.get("goals") or []:
            if str(row.get("id")) == str(goal_id):
                return _score(row)
    return None


# Legacy record dates: yearly "2018", quarterly "2018-04" (year, quarter index).
def _record(record, kpi_id, kpi_name):
    date = str(record.get("ethio_date") or "")
    year, _, quarter = date.partition("-")
    is_quarterly = record.get("record_type") == "quarterly"
    row = {
        "id": record.get("id"),
        "year": int(year) if year.isdigit() else year,
        "score": record.get("score"),
        "scorecard": record.get("score_color"),
        "indicator": kpi_id,
        "indicator_name": kpi_name,
    }
    if is_quarterly:
        row["quarter"] = NUMBER_TO_QUARTER.get(int(quarter)) if quarter.isdigit() else quarter
        row["quarter_target"] = record.get("target")
        row["quarter_performance"] = record.get("performance")
    else:
        row["annual_target"] = record.get("target")
        row["annual_performance"] = record.get("performance")
    return row


def indicator(kpi):
    """DPMES KPI (with records) -> legacy indicator shape."""
    kpi_id = kpi.get("id")
    name = _name(kpi)
    records = [r for r in kpi.get("records") or [] if isinstance(r, dict)]
    return {
        "id": kpi_id,
        "kpi_name_eng": name,
        "kpi_name_amh": kpi.get("name_eth") or name,
        "kpi_code": kpi.get("code"),
        "kpi_weight": kpi.get("weight"),
        "kpi_description": kpi.get("description"),
        "kpi_measurement_units": kpi.get("measurement_units"),
        "kpi_characteristics": kpi.get("kpi_characteristics"),
        "annual_indicators": [_record(r, kpi_id, name) for r in records if r.get("record_type") != "quarterly"],
        "quarter_indicators": [_record(r, kpi_id, name) for r in records if r.get("record_type") == "quarterly"],
    }


def range_for_score(score, ranges):
    """The DPMES score range a value falls in, or the default (No Data) range."""
    default = next((r for r in ranges if r.get("is_default")), None)
    if score is None:
        return default
    for band in ranges:
        try:
            if float(band["start"]) <= float(score) <= float(band["end"]):
                return band
        except (KeyError, TypeError, ValueError):
            continue
    return default


# DPMES grades KPIs into six ranges; the legacy pages have four cards.
RANGE_TO_GOAL_BUCKET = {
    "Achieved": "good_performance",
    "On Track": "good_performance",
    "In Progress": "average_performance",
    "Weak Performance": "poor_performance",
    "Requires Intervention": "poor_performance",
    "No Data": "no_performance",
}
RANGE_TO_BODY_BUCKET = {
    "Achieved": "on_track",
    "On Track": "on_track",
    "In Progress": "in_progress",
    "Weak Performance": "weak_performance",
    "Requires Intervention": "weak_performance",
    "No Data": "no_data",
}


def _range_name(band):
    return (band or {}).get("name_en") or (band or {}).get("trans_name") or "No Data"


def goal_detail(data, ranges, goal_score=None):
    """goals/{id}/kras/ -> legacy goal-detail payload.

    The KRA endpoint has no goal-level score; callers pass the authoritative one
    from the organization scorecard. Without it we derive the weighted average
    from the KRAs, which can differ from DPMES in the last decimal.
    """
    kras = []
    total_score = total_weight = 0.0
    buckets = {key: [] for key in set(RANGE_TO_GOAL_BUCKET.values())}

    for kra in data.get("kras") or []:
        if not isinstance(kra, dict):
            continue
        raw_score = kra.get("score") or {}
        total_score += float(raw_score.get("total_score") or 0)
        total_weight += float(raw_score.get("total_weight") or 0)

        indicators = [indicator(kpi) for kpi in kra.get("kpis") or [] if isinstance(kpi, dict)]
        for item in indicators:
            latest = (item["quarter_indicators"] or item["annual_indicators"] or [None])[0]
            band = range_for_score(latest and latest.get("score"), ranges)
            if latest is None:
                latest = {"indicator": item["id"], "indicator_name": item["kpi_name_eng"], "score": None}
            buckets[RANGE_TO_GOAL_BUCKET.get(_range_name(band), "no_performance")].append(
                {**latest, "scorecard": latest.get("scorecard") or (band or {}).get("color")}
            )

        name = _name(kra)
        kras.append({
            "id": kra.get("id"),
            "activity_name_eng": name,
            "activity_name_amh": kra.get("name_eth") or name,
            "code": kra.get("code"),
            "kra_score_card": _score(kra),
            "indicators": indicators,
        })

    if goal_score is None:
        avg = round(total_score / total_weight * 100, 2) if total_weight else None
        band = range_for_score(avg, ranges)
        goal_score = {"avg_score": avg, "scorecard_color": (band or {}).get("color"), "total_weight": total_weight or None}

    total = sum(len(rows) for rows in buckets.values())
    name = _name(data)
    detail = {
        "id": data.get("id"),
        "goal_name_eng": name,
        "goal_name_amh": data.get("name_eth") or name,
        "code": data.get("code"),
        "goal_score_card": goal_score,
        "kra_goal": kras,
    }
    for key, rows in buckets.items():
        # Target/actual totals have no equivalent in the new API; the cards
        # show the share of KPIs in each band instead.
        detail[key] = {
            "percentage": round(len(rows) / total * 100, 2) if total else 0,
            "target": None,
            "performance": None,
            "count": len(rows),
            "data": rows,
        }
    return detail


def organization_performance(score_ranges_with_kpis):
    """kpis_by_score_range/ -> legacy ministry-performance buckets."""
    buckets = {key: [] for key in set(RANGE_TO_BODY_BUCKET.values())}
    for band in score_ranges_with_kpis or []:
        if not isinstance(band, dict):
            continue
        key = RANGE_TO_BODY_BUCKET.get(_range_name(band), "no_data")
        for kpi in band.get("kpis") or []:
            if not isinstance(kpi, dict):
                continue
            record = next((r for r in kpi.get("records") or [] if isinstance(r, dict)), {})
            buckets[key].append({
                "indicator": kpi.get("id"),
                "indicator_name": _name(kpi),
                "score": record.get("score"),
                "scorecard": record.get("score_color") or band.get("color"),
            })
    return buckets


# --- Overview (mobile home) ----------------------------------------------
#
# The old /dashboard/ministries/ and /dashboard/policy-area/ responses were
# never recorded, so this is a new shape, documented in
# docs/dpmes-overview-api.md. `items` reuses the list endpoints' objects so
# the app can parse them with the models it already has.


def overview_period(query_params, current_year):
    """Like build_period, but defaults to the last completed year, matching
    /default-time/, since the current year is mostly unreported."""
    params = query_params.dict() if hasattr(query_params, "dict") else dict(query_params)
    if params.get("year") in (None, ""):
        params["year"] = current_year - 1
    return build_period(params)


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _active_plan(plan_rows, requested=None):
    rows = [r for r in plan_rows or [] if isinstance(r, dict)]
    if requested not in (None, ""):
        chosen = next((r for r in rows if str(r.get("id")) == str(requested)), None)
    else:
        chosen = next((r for r in rows if r.get("is_active")), rows[0] if rows else None)
    if not chosen:
        return None
    return {key: chosen.get(key) for key in ("id", "code", "name", "name_eth", "start_year", "end_year")}


def _brief(item, title_key, score_key):
    score = item[score_key]
    return {
        "id": item.get("id"),
        "name": item.get(title_key),
        "code": item.get("code"),
        "avg_score": score.get("avg_score"),
        "scorecard_color": score.get("scorecard_color"),
    }


def overview(items, *, title_key, score_key, national, counts, ranges, plan_rows, period):
    """Assemble the overview payload from already-mapped list items."""
    scored = [i for i in items if _float(i[score_key].get("avg_score")) is not None]

    distribution = []
    for band in ranges or []:
        distribution.append({
            "name": band.get("name_en") or band.get("trans_name"),
            "name_eth": band.get("name_eth"),
            "color": band.get("color"),
            "start": _float(band.get("start")),
            "end": _float(band.get("end")),
            "count": 0,
        })
    for item in items:
        band = range_for_score(item[score_key].get("avg_score"), ranges or [])
        name = (band or {}).get("name_en") or (band or {}).get("trans_name")
        for row in distribution:
            if row["name"] == name:
                row["count"] += 1
                break

    ordered = sorted(scored, key=lambda i: _float(i[score_key]["avg_score"]), reverse=True)
    national_score = (national or {}).get("score") or {}
    cards = counts or {}

    return {
        # Integers throughout so a typed client model sees one type per field.
        "period": {
            key: int(period[key]) if str(period.get(key, "")).isdigit() else None
            for key in ("year", "quarter", "month", "plan")
        },
        "plan": _active_plan(plan_rows, period.get("plan")),
        "national": {
            "id": (national or {}).get("id"),
            "name": _name(national or {}),
            "name_eth": (national or {}).get("name_eth"),
            "code": (national or {}).get("code"),
            "icon": (national or {}).get("icon"),
            "avg_score": national_score.get("avg_score"),
            "scorecard_color": national_score.get("color"),
        },
        "counts": {
            "organizations": cards.get("organization"),
            "strategic_goals": cards.get("strategic_goals"),
            "key_result_areas": cards.get("key_result_areas"),
            "key_performance_indicators": cards.get("key_performance_indicators"),
        },
        "score_ranges": distribution,
        "summary": {
            "total": len(items),
            "scored": len(scored),
            "average": round(sum(_float(i[score_key]["avg_score"]) for i in scored) / len(scored), 2) if scored else None,
            "highest": _brief(ordered[0], title_key, score_key) if ordered else None,
            "lowest": _brief(ordered[-1], title_key, score_key) if ordered else None,
        },
        "items": items,
    }
