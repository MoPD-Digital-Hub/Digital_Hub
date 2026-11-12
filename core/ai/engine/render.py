"""Tables and charts built from tool results, never by the model.

Output uses the HTML the web and mobile clients already render: <h4>, <table>,
<chart-data> JSON blocks (bar / line / pie, and the ministry_detail button), and
a <p class="ai-source"> line naming where the block's figures come from.

A chart-data block may also carry "series" (several named lines); clients that
do not read it still get the first line in "labels"/"data".
"""

import json
from html import escape

from integrations.dpmes.compat import NUMBER_TO_QUARTER

FREQUENCY_ORDER = ("monthly", "quarterly", "annual")
MAX_CHART_POINTS = 15
# Up to this many series read best as columns by year; more (regions) as one row each.
MAX_SERIES_COLUMNS = 4


def _fmt(value):
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:,}" if isinstance(value, int) else escape(str(value))


def _coloured(value, color):
    text = _fmt(value)
    return f'<span style="color: {escape(color)}">{text}</span>' if color else text


def _table(headers, rows):
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _chart(payload):
    # JSON leaves <, > and & as-is; a name containing "</chart-data><img …>"
    # would otherwise break out into the page. The escapes decode identically.
    body = json.dumps(payload, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<chart-data>{body}</chart-data>"


def _numeric(points):
    return [p for p in points if isinstance(p.get("value"), (int, float))]


def _indicator_series(result):
    indicator = result["data"]["indicator"]
    unit = f" ({indicator['unit']})" if indicator.get("unit") else ""
    parts = []
    for frequency in FREQUENCY_ORDER:
        points = result["data"]["series"].get(frequency)
        if not points:
            continue
        parts.append(f"<h4>{escape(indicator['name'])}: {frequency}</h4>")
        parts.append(_table(["Period", f"Value{unit}"], [[escape(p["period"]), _fmt(p["value"])] for p in points]))
        chartable = _numeric(points)[-MAX_CHART_POINTS:]
        if len(chartable) > 1:
            parts.append(_chart({
                "type": "line" if frequency != "annual" or len(chartable) > 6 else "bar",
                "label": indicator["name"] + unit,
                "frequency": frequency,
                "labels": [p["period"] for p in chartable],
                "data": [p["value"] for p in chartable],
            }))
    return parts


def _score_block(result, entity_key, items_key, item_label):
    data = result["data"]
    score = data["score"]
    parts = [f"<h4>{escape(result['title'])}, {escape(result.get('period', ''))}</h4>"]
    if data.get(items_key):
        rows = [[escape(item["name"] or ""), _coloured(item["value"], item.get("color"))] for item in data[items_key]]
        parts.append(_table([item_label, "Score (%)"], rows))
    if score.get("value") is not None:
        parts.append(_chart({
            "type": "pie", "label": f"{data[entity_key]['name']} overall score",
            "labels": score.get("band") or "Score", "data": str(score["value"]),
            "score_color": score.get("color") or "",
        }))
    return parts, data


def _organization_score(result):
    parts, data = _score_block(result, "organization", "policy_areas", "Policy area")
    period = data["period"]
    button = {"type": "button", "button_type": "ministry_detail", "id": data["organization"]["id"],
              "year": str(period["year"])}
    if period.get("quarter"):
        button["quarter"] = NUMBER_TO_QUARTER[period["quarter"]]
    parts.append(_chart(button))
    return parts


def _policy_area_score(result):
    parts, _ = _score_block(result, "policy_area", "goals", "Goal")
    return parts


def _kpi_list(result):
    data = result["data"]
    if not data["kpis"]:
        return []
    parts = [f"<h4>{escape(result['title'])}, {escape(result.get('period', ''))}</h4>"]
    parts.append(_table(["KPI", "Score (%)"], [[escape(k["name"] or ""), _coloured(k["value"], k.get("color"))] for k in data["kpis"]]))
    chartable = _numeric(data["kpis"])[:MAX_CHART_POINTS]
    if len(chartable) > 1:
        parts.append(_chart({"type": "bar", "label": "KPI score (%)", "labels": [k["name"] for k in chartable],
                             "data": [k["value"] for k in chartable]}))
    return parts


def _goal_detail(result):
    data = result["data"]
    if not data["key_result_areas"]:
        return []
    parts = [f"<h4>{escape(result['title'])}: key result areas, {escape(result.get('period', ''))}</h4>"]
    rows = [[escape(k["name"] or ""), _coloured(k["value"], k.get("color")), _fmt(k["kpis"])] for k in data["key_result_areas"]]
    parts.append(_table(["Key result area", "Score (%)", "KPIs"], rows))
    return parts


def _ranking(result):
    data = result["data"]
    if not data["items"]:
        return []
    parts = [f"<h4>{escape(result['title'])}, {escape(result.get('period', ''))}</h4>"]
    rows = [[str(i + 1), escape(item["name"] or ""), _coloured(item["value"], item.get("color"))] for i, item in enumerate(data["items"])]
    parts.append(_table(["#", "Name", "Score (%)"], rows))
    parts.append(_chart({"type": "bar", "label": "Score (%)", "labels": [i["name"] for i in data["items"]],
                         "data": [i["value"] for i in data["items"]]}))
    return parts


def _sdg_indicator(result):
    data = result["data"]
    series = data["series"]
    unit = data["indicator"].get("unit")
    unit_text = f" ({unit})" if unit else ""
    parts = [f"<h4>{escape(result['title'])}, {escape(result.get('period', ''))}</h4>"]

    if len(series) <= MAX_SERIES_COLUMNS:
        years = sorted({p["year"] for s in series for p in s["points"]})
        values = [{p["year"]: p["value"] for p in s["points"]} for s in series]
        headers = ["Year"] + ([f"Value{unit_text}"] if len(series) == 1 else [f"{s['name']}{unit_text}" for s in series])
        rows = [[str(year)] + [_fmt(v.get(year)) for v in values] for year in years]
        parts.append(_table(headers, rows))
        first = series[0]["points"][-MAX_CHART_POINTS:]
        if len(years) > 1:
            chart = {
                "type": "line" if len(years) > 2 else "bar",
                "label": data["indicator"]["name"] + unit_text,
                "labels": [str(p["year"]) for p in first],
                "data": [p["value"] for p in first],
            }
            if len(series) > 1:
                chart["label"] += f" – {series[0]['name']}"
                chart["series"] = [{"name": s["name"], "points": [[str(p["year"]), p["value"]] for p in s["points"]]}
                                   for s in series]
            parts.append(_chart(chart))
        return parts

    # Many series (one per region, age group…): the latest value of each.
    label = series[0].get("dimension") or "Series"
    latest = [(s["name"], s["points"][-1]) for s in series]
    parts.append(_table([label, f"Latest value{unit_text}", "Year"],
                        [[escape(name), _fmt(point["value"]), str(point["year"])] for name, point in latest]))
    parts.append(_chart({"type": "bar", "label": data["indicator"]["name"] + unit_text + ", latest value",
                         "labels": [name for name, _ in latest], "data": [point["value"] for _, point in latest]}))
    return parts


def _sdg_goal(result):
    rows = result["data"]["indicators"]
    if not rows:
        return []
    parts = [f"<h4>{escape(result['title'])}</h4>"]
    parts.append(_table(["Indicator", "Value", "Unit", "Year"], [
        [escape(f"{r['code']} {r['name']}" + (f" ({r['series']})" if r.get("series") else "")),
         _fmt(r["value"]), escape(r.get("unit") or ""), str(r["year"])]
        for r in rows
    ]))
    return parts


# Which of the three sources a tool reads; clients may colour blocks by it.
SOURCE_KINDS = {
    "indicator_series": "time_series",
    "organization_score": "dpmes", "organization_kpis": "dpmes", "policy_area_score": "dpmes",
    "goal_detail": "dpmes", "rank_organizations": "dpmes", "rank_policy_areas": "dpmes",
    "sdg_indicator": "sdg", "sdg_goal": "sdg",
}


def _sdg_goal_number(result):
    """The SDG (1-17) an SDG result belongs to, as a string, or ""."""
    data = result.get("data") or {}
    if result.get("tool") == "sdg_goal":
        value = (data.get("goal") or {}).get("id")
    elif result.get("tool") == "sdg_indicator":
        value = str((data.get("indicator") or {}).get("code") or "").split(".")[0]
    else:
        return ""
    value = str(value or "").strip()
    return value if value.isdigit() and 1 <= int(value) <= 17 else ""


def _source(result):
    """"Source: Ethiopia's national SDG platform (sdg.mopd.gov.et; original data: EDHS, MoH)"."""
    source = result.get("source")
    if not source:
        return ""
    detail = "; ".join(filter(None, [
        result.get("source_detail"),
        f"original data: {result['original_data']}" if result.get("original_data") else "",
    ]))
    kind = SOURCE_KINDS.get(result.get("tool"), "")
    attribute = f' data-source="{kind}"' if kind else ""
    goal = _sdg_goal_number(result)
    if goal:
        # Lets clients show the goal's icon; the mobile app ignores it.
        attribute += f' data-sdg-goal="{goal}"'
    return (f'<p class="ai-source"{attribute}>Source: {escape(str(source))}'
            + (f" ({escape(detail)})" if detail else "") + "</p>")


def web_sources(pages):
    """The source line of a web-searched answer: the pages, numbered as the text cites them.

    <p class="ai-source" data-source="web">Source: the web: <a href="…">[1] imf.org</a> <a …>[2] …</a></p>
    """
    links = []
    for i, page in enumerate(pages):
        url = str(page.get("url") or "")
        if not url.startswith(("https://", "http://")):
            continue
        links.append(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer" '
                     f'title="{escape(str(page.get("title") or url), quote=True)}">[{i + 1}] {escape(str(page.get("site") or url))}</a>')
    if not links:
        return ""
    return f'<p class="ai-source" data-source="web">Source: the web: {" ".join(links)}</p>'


RENDERERS = {
    "indicator_series": _indicator_series,
    "organization_score": _organization_score,
    "organization_kpis": _kpi_list,
    "policy_area_score": _policy_area_score,
    "goal_detail": _goal_detail,
    "rank_organizations": _ranking,
    "rank_policy_areas": _ranking,
    "sdg_indicator": _sdg_indicator,
    "sdg_goal": _sdg_goal,
}


def sections(results):
    """HTML for every successful tool result, in call order."""
    html = []
    for result in results:
        renderer = RENDERERS.get(result.get("tool"))
        parts = renderer(result) if renderer else []
        if parts:
            html.extend(parts)
            html.append(_source(result))
    return "".join(html)
