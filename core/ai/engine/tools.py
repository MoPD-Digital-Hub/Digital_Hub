"""Typed data tools. Each fetches one kind of fact and returns it structured.

No model is involved here: the planner picks tools and names entities, the
catalog resolves the names, and these functions do the lookups. Results are
cached briefly so a follow-up question does not refetch.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable

import requests
from django.core.cache import cache

from ai.engine import periods
from ai.models import CatalogEntity
from integrations.dpmes import client as dpmes_client
from integrations.dpmes import compat as dpmes_compat
from integrations.sdg import client as sdg_client
from integrations.sdg import series as sdg_series
from integrations.time_series import client as time_series_client

CACHE_SECONDS = 300
MAX_KPIS = 25
MAX_RANKED = 10
MAX_SDG_ROWS = 30


class ToolError(Exception):
    """A lookup failed; the message is safe to show the user."""


@dataclass
class Tool:
    name: str
    description: str
    run: Callable
    # Arguments that must resolve to catalog entities, and their kinds.
    entities: dict = field(default_factory=dict)
    optional_entities: tuple = ()


def _cached(key_parts, loader):
    key = "ai-tool:" + hashlib.sha1(json.dumps(key_parts, sort_keys=True, default=str).encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    value = loader()
    cache.set(key, value, CACHE_SECONDS)
    return value


def _dpmes(call, *args):
    try:
        return _cached([call.__name__, *args], lambda: call(*args))
    except dpmes_client.DPMES2Error as exc:
        raise ToolError(f"DPMES could not provide this data ({exc}).") from exc


def _score(raw):
    raw = raw or {}
    return {"value": raw.get("avg_score"), "color": raw.get("color")}


def _band_name(score):
    ranges = _dpmes(dpmes_client.score_ranges) or []
    band = dpmes_compat.range_for_score(score, ranges)
    return (band or {}).get("name_en") or (band or {}).get("trans_name")


def _kpi_counts(performance_analysis):
    return {band: values[0] for band, values in (performance_analysis or {}).items() if values}


# --- Time series -----------------------------------------------------------


def indicator_series(*, indicator, year=None, **_):
    code = indicator.code or indicator.external_id

    def load():
        try:
            response = time_series_client.annual_value(code)
        except requests.RequestException as exc:
            raise ToolError(f"The time-series service is unreachable ({exc}).") from exc
        if response.status_code == 400:
            raise ToolError(f"The time-series service has no data for {indicator.name} ({code}).")
        if response.status_code >= 400:
            raise ToolError(f"The time-series service returned HTTP {response.status_code}.")
        return response.json()

    payload = _cached(["series", code], load)
    raw = payload.get("time_series") or {}
    # The API lists newest first; tables and charts read oldest to newest.
    series = {
        "annual": [{"period": str(p["year"]), "value": p.get("value")} for p in reversed(raw.get("annual") or [])],
        "quarterly": [{"period": f"{p['year']} {p.get('quarter')}", "value": p.get("value")} for p in reversed(raw.get("quarter") or [])],
        "monthly": [{"period": f"{periods.month_label(p.get('month'))} {p['year']}", "value": p.get("value")} for p in reversed(raw.get("month") or [])],
    }
    series = {k: v for k, v in series.items() if v}
    details = indicator.details or {}
    notes, requested = [], None
    if year:
        ethiopian, converted = periods.to_ethiopian_year(year)
        if converted:
            notes.append(f"{year} was read as a Gregorian year and looked up as {ethiopian} EC.")
        value = next((p["value"] for p in series.get("annual", []) if p["period"] == str(ethiopian)), None)
        requested = {"year": ethiopian, "value": value}
        if value is None:
            notes.append(f"There is no annual value for {ethiopian} EC.")

    return {
        "tool": "indicator_series",
        "title": indicator.name,
        "source": details.get("source") or "MoNS time-series database",
        "notes": notes,
        "data": {
            "indicator": {"name": indicator.name, "code": code, "unit": details.get("unit"),
                          "frequency": details.get("frequency"), "description": details.get("description")},
            "requested": requested,
            "series": series,
        },
    }


# --- DPMES -----------------------------------------------------------------


def organization_score(*, organization, year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    card = _dpmes(dpmes_client.organization_scorecard, organization.external_id, period) or {}
    score = _score(card.get("score"))
    return {
        "tool": "organization_score",
        "title": f"{organization.name}: performance score",
        "source": "DPMES",
        "notes": notes,
        "period": periods.period_label(period),
        "data": {
            "organization": {"id": organization.external_id, "name": organization.name, "code": organization.code},
            "period": period,
            "score": {**score, "band": _band_name(score["value"])},
            "policy_areas": [
                {"name": area.get("name"), **_score(area.get("score"))}
                for area in card.get("policy_areas") or []
            ],
            "kpi_counts": _kpi_counts(card.get("performance_analysis")),
        },
    }


PERFORMANCE_BUCKETS = {"on_track": "on_track", "in_progress": "in_progress", "weak": "weak_performance", "no_data": "no_data"}


def organization_kpis(*, organization, performance="all", year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    rows = _dpmes(dpmes_client.kpis_by_score_range, organization.external_id, period)
    buckets = dpmes_compat.organization_performance(rows)
    counts = {key: len(buckets.get(bucket, [])) for key, bucket in PERFORMANCE_BUCKETS.items()}
    bucket = PERFORMANCE_BUCKETS.get(performance)
    records = buckets.get(bucket, []) if bucket else [r for rs in buckets.values() for r in rs]
    worst_first = performance in ("weak", "no_data")
    records = sorted(
        records,
        key=lambda r: r.get("score") if r.get("score") is not None else -1,
        reverse=not worst_first,
    )
    return {
        "tool": "organization_kpis",
        "title": f"{organization.name}: KPIs" + (f" ({performance.replace('_', ' ')})" if bucket else ""),
        "source": "DPMES",
        "notes": notes + ([f"Showing {MAX_KPIS} of {len(records)} KPIs."] if len(records) > MAX_KPIS else []),
        "period": periods.period_label(period),
        "data": {
            "organization": {"id": organization.external_id, "name": organization.name, "code": organization.code},
            "period": period,
            "performance": performance if bucket else "all",
            "counts": counts,
            "kpis": [
                {"name": r.get("indicator_name"), "value": r.get("score"), "color": r.get("scorecard")}
                for r in records[:MAX_KPIS]
            ],
        },
    }


def policy_area_score(*, policy_area, year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    card = _dpmes(dpmes_client.policy_area_scorecard, policy_area.external_id, period) or {}
    score = _score(card.get("score"))
    return {
        "tool": "policy_area_score",
        "title": f"{policy_area.name}: performance score",
        "source": "DPMES",
        "notes": notes,
        "period": periods.period_label(period),
        "data": {
            "policy_area": {"id": policy_area.external_id, "name": policy_area.name, "code": policy_area.code},
            "period": period,
            "score": {**score, "band": _band_name(score["value"])},
            "goals": [{"name": g.get("name"), **_score(g.get("score"))} for g in card.get("goals") or []],
            "kpi_counts": _kpi_counts(card.get("performance_analysis")),
        },
    }


def goal_detail(*, goal, organization=None, year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    org_id = organization.external_id if organization else _dpmes(dpmes_client.key_organization_id)
    if organization is None:
        notes.append("No organization was named, so the national view is used.")
    kras = (_dpmes(dpmes_client.goal_kras, goal.external_id, org_id, period) or {}).get("kras") or []
    goal_score = dpmes_compat.find_goal_score(_dpmes(dpmes_client.organization_scorecard, org_id, period), goal.external_id)
    return {
        "tool": "goal_detail",
        "title": f"{goal.name}",
        "source": "DPMES",
        "notes": notes,
        "period": periods.period_label(period),
        "data": {
            "goal": {"id": goal.external_id, "name": goal.name, "code": goal.code,
                     "policy_area": (goal.details or {}).get("policy_area")},
            "organization": organization.name if organization else "National",
            "period": period,
            "score": {"value": (goal_score or {}).get("avg_score"), "color": (goal_score or {}).get("scorecard_color")},
            "key_result_areas": [
                {"name": k.get("name"), **_score(k.get("score")), "kpis": len(k.get("kpis") or [])}
                for k in kras
            ],
        },
    }


def _ranked(title, rows, order, period, notes):
    scored = [
        {"name": r.get("name") or r.get("trans_name"), **_score(r.get("score"))}
        for r in rows or []
        if (r.get("score") or {}).get("avg_score") is not None
    ]
    scored.sort(key=lambda r: r["value"], reverse=(order != "bottom"))
    return {
        "title": title, "source": "DPMES", "notes": notes, "period": periods.period_label(period),
        "data": {"period": period, "order": order, "total": len(scored), "items": scored[:MAX_RANKED]},
    }


def rank_organizations(*, order="top", year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    rows = _dpmes(dpmes_client.child_organizations, period)
    return {"tool": "rank_organizations", **_ranked(
        "Public bodies ranked by performance score", rows, order, period, notes)}


def rank_policy_areas(*, order="top", year=None, quarter=None, **_):
    period, notes = periods.dpmes_period(year, quarter)
    rows = _dpmes(dpmes_client.policy_area_scores, period)
    return {"tool": "rank_policy_areas", **_ranked(
        "Policy areas ranked by performance score", rows, order, period, notes)}


# --- National SDG platform ---------------------------------------------------


def _sdg_goal(goal_id):
    try:
        return sdg_client.goal(goal_id)
    except sdg_client.SDGError as exc:
        raise ToolError(f"The national SDG platform could not provide this data ({exc}).") from exc


def _original_data(items):
    """The surveys or records behind the platform's figures ("Ethiopia DHS, MoH")."""
    origins = []
    for item in items:
        for value in [*(item.get("sources") or []), *(item.get("providers") or [])]:
            for part in str(value or "").split(","):
                part = part.strip()
                if part and part not in origins:
                    origins.append(part)
    return ", ".join(origins[:4])


def sdg_indicator(*, sdg_indicator, year=None, breakdown=None, **_):
    details = sdg_indicator.details or {}
    feed = _sdg_goal(details.get("goal") or sdg_indicator.code.split(".")[0])
    matches = [i for i in feed["indicators"] if str(i.get("id")) == sdg_indicator.external_id]
    # The platform lists a few indicators twice (11.b.2); prefer the copy with data.
    item = next((i for i in matches if i.get("data")), matches[0] if matches else None)
    if item is None:
        raise ToolError(f"The national SDG platform no longer lists indicator {sdg_indicator.external_id}.")

    notes = []
    if not item.get("data"):
        # Global indicators often have no data of their own; their proxy or
        # additional indicators (1.1.1P1 for 1.1.1) carry the figures.
        children = [i for i in feed["indicators"] if i.get("parentIndicator") == item.get("id") and i.get("data")]
        if not children:
            raise ToolError(f"The national SDG platform has no data for SDG indicator {item.get('id')} yet.")
        child = children[0]
        notes.append(f"SDG {item.get('id')} has no data of its own; its {str(child.get('type') or 'related').lower()} "
                     f"indicator {child.get('id')} ({child.get('description')}) is shown.")
        item = child

    shown, series_notes = sdg_series.select(item["data"], breakdown)
    notes += series_notes
    if not shown:
        raise ToolError(f"The national SDG platform has no figures for SDG indicator {item.get('id')}.")

    requested = None
    if year:
        values = [{"series": s["name"], "value": p["value"]} for s in shown for p in s["points"] if p["year"] == int(year)]
        requested = {"year": int(year), "values": values}
        if not values:
            notes.append(f"There is no value for {year}; years with data: "
                         f"{', '.join(str(y) for y in sorted({p['year'] for s in shown for p in s['points']}))}.")
    years = sorted({p["year"] for s in shown for p in s["points"]})
    return {
        "tool": "sdg_indicator",
        "title": f"{item.get('description')}: SDG {item.get('id')}",
        "source": sdg_client.SOURCE_NAME,
        "source_detail": sdg_client.SOURCE_SITE,
        "original_data": _original_data([item]),
        "calendar": "Gregorian",
        "notes": notes,
        "period": f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]),
        "data": {
            "indicator": {
                "code": item.get("id"), "name": item.get("description"), "type": item.get("type"),
                "goal": f"SDG {item.get('goal')}: {(feed.get('goal') or {}).get('goal')}",
                "target": item.get("target"), "unit": shown[0]["unit"],
            },
            "breakdown": breakdown if breakdown in sdg_series.BREAKDOWNS else None,
            "requested": requested,
            "series": shown,
        },
    }


def sdg_goal(*, sdg_goal, **_):
    feed = _sdg_goal(sdg_goal.external_id)
    goal = feed.get("goal") or {}
    rows, reported = [], []
    for item in feed["indicators"]:
        series = sdg_series.headline(item.get("data")) if item.get("data") else None
        if not series:
            continue
        latest = series["points"][-1]
        reported.append(item)
        rows.append({
            "code": item.get("id"), "name": item.get("description"),
            "series": None if series["name"] == "Total" else series["name"],
            "value": latest["value"], "unit": series["unit"], "year": latest["year"],
        })
    notes = [f"Showing {MAX_SDG_ROWS} of {len(rows)} indicators with data."] if len(rows) > MAX_SDG_ROWS else []
    return {
        "tool": "sdg_goal",
        "title": f"SDG {goal.get('id', sdg_goal.external_id)} {goal.get('goal') or sdg_goal.name}: latest values",
        "source": sdg_client.SOURCE_NAME,
        "source_detail": sdg_client.SOURCE_SITE,
        "original_data": _original_data(reported),
        "calendar": "Gregorian",
        "notes": notes,
        "data": {
            "goal": {"id": goal.get("id"), "name": goal.get("goal"), "description": goal.get("description")},
            "indicators_total": len(feed["indicators"]),
            "indicators_with_data": len(rows),
            "indicators": rows[:MAX_SDG_ROWS],
        },
    }


TOOLS = {tool.name: tool for tool in (
    Tool("indicator_series", "Values over time of a national statistical indicator (GDP, inflation, "
         "production, exports, health, education…). Args: indicator, optional year.",
         indicator_series, {"indicator": CatalogEntity.INDICATOR}),
    Tool("organization_score", "Overall DPMES performance score of one ministry or agency, with its policy "
         "area scores. Args: organization, optional year, quarter.",
         organization_score, {"organization": CatalogEntity.ORGANIZATION}),
    Tool("organization_kpis", "KPIs of one ministry or agency, optionally only those on_track, in_progress, "
         "weak or no_data. Args: organization, performance, optional year, quarter.",
         organization_kpis, {"organization": CatalogEntity.ORGANIZATION}),
    Tool("policy_area_score", "Performance score of one national policy area with its goals. "
         "Args: policy_area, optional year, quarter.",
         policy_area_score, {"policy_area": CatalogEntity.POLICY_AREA}),
    Tool("goal_detail", "One strategic goal with its key result areas, optionally for one organization. "
         "Args: goal, optional organization, year, quarter.",
         goal_detail, {"goal": CatalogEntity.GOAL}, optional_entities=("organization",)),
    Tool("rank_organizations", "Ministries and agencies ranked by score (best or worst). Args: order top|bottom, "
         "optional year, quarter.", rank_organizations),
    Tool("rank_policy_areas", "Policy areas ranked by score (best or worst). Args: order top|bottom, "
         "optional year, quarter.", rank_policy_areas),
    Tool("sdg_indicator", "Values over the years of one SDG indicator from the national SDG platform (poverty "
         "headcount, stunting, school completion, access to water and sanitation…), nationally or broken "
         "down. Args: sdg_indicator (its name or number, e.g. 1.1.1), optional year, breakdown "
         "region|sex|age|location|education|wealth.",
         sdg_indicator, {"sdg_indicator": CatalogEntity.SDG_INDICATOR}),
    Tool("sdg_goal", "Progress on one Sustainable Development Goal: the latest national value of each of its "
         "indicators. Args: sdg_goal (its name or number, e.g. SDG 4 or quality education).",
         sdg_goal, {"sdg_goal": CatalogEntity.SDG_GOAL}),
)}
