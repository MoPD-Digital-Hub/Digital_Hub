"""Where an answer's charts and tables go.

The writer places each dataset where it supports the text, with a marker on its
own line: [[chart:N]] / [[table:N]] (light, inline), [[figure:N]] (a compact
card), [[card:N]] (the full data panel) or [[visual:N]] (the best view). N is the result's number in the
facts. Code swaps the marker for that result's blocks, rendered from the data
exactly as before (render.py), so the model never writes a figure into a chart.

The view rides on the block's title, <h4 data-view="chart|table|figure|card">, and a
result the writer did not place is still sent, after the text, marked
<h4 data-placement="more"> (the web chat folds those under "Show all data").
Clients that ignore the attributes (the mobile app) see the same <h4>, <table>
and <chart-data> elements as before, only in better places. Answers saved before
markers existed have no attributes and show as they always did.
"""

import re

from ai.engine import render

MARKER = re.compile(r"\[\[\s*(chart|table|figure|card|visual)\s*:\s*(\d{1,2})\s*\]\]", re.IGNORECASE)
# Tables the writer makes itself (a short comparison) stay in the text, not in a data panel.
WRITER_TABLE = re.compile(r"<table(?![^>]*\bclass=)", re.IGNORECASE)
EMPTY_PARAGRAPH = re.compile(r"<p>\s*</p>\s*")
# A marker can arrive split across streamed pieces ("[[cha" + "rt:0]]"): hold back
# up to this much text after an unclosed "[[".
MAX_MARKER = 24

# The view that suits each kind of result, for [[visual:N]] and unplaced results.
BEST_VIEW = {
    "indicator_series": "chart",
    "sdg_indicator": "chart",
    "organization_score": "figure",
    "policy_area_score": "figure",
    "organization_kpis": "table",
    "goal_detail": "table",
    "rank_organizations": "table",
    "rank_policy_areas": "table",
    "sdg_goal": "table",
}


def best_view(result):
    return BEST_VIEW.get(result.get("tool"), "table")


# A marker still being written ("[[chart:"), at the end of the text so far.
PARTIAL_MARKER = re.compile(r"\[\[[^\]\n]{0,%d}\]?$" % MAX_MARKER)


def strip_markers(text, partial=False):
    """The text without its markers; `partial` also drops one that is not finished yet (live drafts)."""
    text = MARKER.sub(" ", str(text or ""))
    return PARTIAL_MARKER.sub("", text) if partial else text


def _blocks(result, view=None, placement=None):
    """The result's chat blocks (title, table, chart, source); the title carries the view and placement."""
    renderer = render.RENDERERS.get(result.get("tool"))
    parts = renderer(result) if renderer else []
    if not parts:
        return ""
    attributes = (f' data-view="{view}"' if view else "") + (f' data-placement="{placement}"' if placement else "")
    if attributes:
        parts = [part.replace("<h4>", f"<h4{attributes}>", 1) if part.startswith("<h4>") else part for part in parts]
    return "".join(parts) + render._source(result)


class Placer:
    """Swaps markers for visuals as the writer's text streams in."""

    def __init__(self, results):
        self.results = list(results)
        self.placed = set()
        self.buffer = ""
        self.open_paragraphs = 0

    def _visual(self, kind, index):
        if not 0 <= index < len(self.results) or index in self.placed:
            return ""
        result = self.results[index]
        view = best_view(result) if kind == "visual" else kind
        html = _blocks(result, view)
        if html:
            self.placed.add(index)
        return html

    def _emit(self, text):
        """Text with its markers replaced; a visual never lands inside an open paragraph."""
        text = WRITER_TABLE.sub('<table class="ai-text-table"', text)
        out, position = [], 0
        for match in MARKER.finditer(text):
            before = text[position:match.start()]
            out.append(before)
            self._track(before)
            html = self._visual(match.group(1).lower(), int(match.group(2)))
            if html:
                if self.open_paragraphs > 0:
                    html = "</p>" + html + "<p>"
                out.append(html)
            position = match.end()
        rest = text[position:]
        out.append(rest)
        self._track(rest)
        # A marker on its own line was a paragraph of its own; drop the empty shells it leaves.
        return EMPTY_PARAGRAPH.sub("", "".join(out))

    def _track(self, text):
        opened = len(re.findall(r"<p[\s>]", text, re.IGNORECASE))
        closed = len(re.findall(r"</p>", text, re.IGNORECASE))
        self.open_paragraphs = max(0, self.open_paragraphs + opened - closed)

    def _hold_from(self):
        """Where a marker that may not be complete yet starts, or None."""
        start = self.buffer.rfind("[[")
        if start != -1 and "]]" not in self.buffer[start:] and len(self.buffer) - start <= MAX_MARKER:
            return start
        if self.buffer.endswith("["):
            return len(self.buffer) - 1
        # A tag split across pieces ("<tab" + "le>"): wait for its end, so writer tables get their class.
        tag = self.buffer.rfind("<")
        if tag != -1 and ">" not in self.buffer[tag:] and len(self.buffer) - tag <= 16:
            return tag
        return None

    def feed(self, piece):
        """What can be sent now; text that may still become a marker is held back."""
        self.buffer += str(piece or "")
        hold = self._hold_from()
        ready, self.buffer = (self.buffer, "") if hold is None else (self.buffer[:hold], self.buffer[hold:])
        return self._emit(ready) if ready else ""

    def flush(self):
        """The rest of the text, once the writer is done."""
        text, self.buffer = self.buffer, ""
        return self._emit(text) if text else ""

    def place(self, text):
        """A whole answer at once (Amharic is written in full before it is sent)."""
        return self.feed(text) + self.flush()

    def remaining(self):
        """Results the writer did not place, after the text, marked for the "Show all data" fold.

        The writer adds a visual only where it helps, so a short answer often has
        none; its data is still there, one click away. Clients that ignore the
        attribute (the mobile app) show it after the text, as they always have.
        """
        return "".join(_blocks(result, best_view(result), "more")
                       for index, result in enumerate(self.results) if index not in self.placed)
