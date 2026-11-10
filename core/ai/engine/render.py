"""Tables and charts built from tool results, never by the model.

Output uses the HTML the web and mobile clients already render: <h4>, <table>,
and <chart-data> JSON blocks (bar / line / pie, and the ministry_detail button).
"""

import json
from html import escape

from integrations.dpmes.compat import NUMBER_TO_QUARTER

FREQUENCY_ORDER = ("monthly", "quarterly", "annual")
MAX_CHART_POINTS = 15


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


RENDERERS = {
    "indicator_series": _indicator_series,
    "organization_score": _organization_score,
    "organization_kpis": _kpi_list,
    "policy_area_score": _policy_area_score,
    "goal_detail": _goal_detail,
    "rank_organizations": _ranking,
    "rank_policy_areas": _ranking,
}


def sections(results):
    """HTML for every successful tool result, in call order."""
    html = []
    for result in results:
        renderer = RENDERERS.get(result.get("tool"))
        if renderer:
            html.extend(renderer(result))
    return "".join(html)
