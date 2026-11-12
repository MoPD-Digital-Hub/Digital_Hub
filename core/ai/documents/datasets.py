"""The charts and tables a document may show, taken from the fetched results.

Each tool result is rendered exactly as in a chat answer (ai.engine.render), and
that output is read back into datasets: a title, a table, a chart and the
source line. So documents show the same figures, in the same shape, as chat.
"""

import json
import re
from html import unescape

from ai.engine import render

TABLE_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
CHART = re.compile(r"<chart-data>(.*?)</chart-data>", re.S)


def _text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(html or "")))).strip()


def _table(html):
    rows = [[_text(cell) for cell in CELL.findall(row)] for row in TABLE_ROW.findall(html)]
    rows = [row for row in rows if row]
    return {"headers": rows[0], "rows": rows[1:]} if rows else None


def _chart(html):
    match = CHART.search(html)
    if not match:
        return None
    try:
        chart = json.loads(match.group(1))
    except ValueError:
        return None
    if chart.get("type") not in ("line", "bar", "area") or not chart.get("labels") or not chart.get("data"):
        return None
    return chart


def build(results):
    """[{"title", "table", "chart", "source"}], one per block a chat answer would show."""
    datasets = []
    for result in results:
        renderer = render.RENDERERS.get(result.get("tool"))
        if not renderer:
            continue
        source = _text(render._source(result))
        current = None
        for part in renderer(result):
            if part.startswith("<h4"):
                current = {"title": _text(part), "table": None, "chart": None, "source": source}
                datasets.append(current)
                continue
            if current is None:
                current = {"title": result.get("title") or "", "table": None, "chart": None, "source": source}
                datasets.append(current)
            if part.startswith("<table"):
                current["table"] = current["table"] or _table(part)
            elif part.startswith("<chart-data"):
                current["chart"] = current["chart"] or _chart(part)
    return [d for d in datasets if d["table"] or d["chart"]]


def summary(datasets, max_points=24):
    """What the outline writer is told about each dataset, so it can choose visuals."""
    lines = []
    for index, dataset in enumerate(datasets):
        item = {"dataset": index, "title": dataset["title"]}
        chart = dataset.get("chart")
        if chart:
            item["chart"] = {"type": chart["type"], "label": chart.get("label"),
                             "values": dict(list(zip(chart["labels"], chart["data"]))[-max_points:])}
        table = dataset.get("table")
        if table:
            item["table"] = {"columns": table["headers"], "rows": table["rows"][:max_points]}
        lines.append(item)
    return json.dumps(lines, ensure_ascii=False, separators=(",", ":"))


def sources(datasets, pages=()):
    """Every source named, once, in order."""
    seen = []
    for dataset in datasets:
        source = re.sub(r"^Source:\s*", "", dataset.get("source") or "")
        if source and source not in seen:
            seen.append(source)
    for page in pages:
        line = f"{page.get('title') or page.get('site')} ({page.get('url')})"
        if line not in seen:
            seen.append(line)
    return seen
