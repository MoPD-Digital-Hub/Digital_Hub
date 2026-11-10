"""Check that every figure in the written answer comes from the fetched data."""

import json
import re
from html import unescape

NUMBER = re.compile(r"(?<![\w#])-?\d+(?:[.,]\d+)*")
TOLERANCE = 0.051


def _numbers(text):
    values = []
    for match in NUMBER.findall(text):
        try:
            values.append(float(match.replace(",", "")))
        except ValueError:
            continue
    return values


def _fact_numbers(results, extra_text=""):
    blob = json.dumps(results, ensure_ascii=False, default=str) + " " + extra_text
    return set(_numbers(blob))


def unsupported_numbers(answer_html, results, question=""):
    """Numbers in the answer that are not in the facts or the question.

    Small whole numbers (counts, ordinals, quarters) are ignored: they are
    usually sentence structure ("two policy areas", "Q3"), not data.
    """
    text = unescape(re.sub(r"<[^>]+>", " ", re.sub(r'style="[^"]*"', "", answer_html or "")))
    allowed = _fact_numbers(results, question)
    # A year inside the span the data covers names a period ("2012 is missing"),
    # it is not a data value.
    years = [v for v in allowed if v.is_integer() and 1900 <= v <= 2100]
    span = (min(years), max(years)) if years else None
    unsupported = []
    for value in _numbers(text):
        if value.is_integer() and abs(value) < 10:
            continue
        if span and value.is_integer() and span[0] <= value <= span[1]:
            continue
        if not any(abs(value - known) <= TOLERANCE for known in allowed):
            unsupported.append(value)
    return unsupported


# Ethiopic, Latin, digits, punctuation and symbols are expected; anything else
# (the model has produced Myanmar letters inside Amharic words) is corruption.
FOREIGN_SCRIPT = re.compile(r"[^\u0000-\u024F\u1200-\u139F\u2D80-\u2DDF\uAB00-\uAB2F\u2000-\u206F\u20A0-\u20CF\u2100-\u214F\u2190-\u21FF\u2600-\u27BF\uFE00-\uFE0F]")


def foreign_script(answer_html):
    """Characters outside the scripts an answer should use, if any."""
    text = unescape(re.sub(r"<[^>]+>", " ", answer_html or ""))
    return sorted(set(FOREIGN_SCRIPT.findall(text)))
