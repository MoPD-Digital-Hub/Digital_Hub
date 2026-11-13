"""The writer's Markdown, turned into the HTML clients render.

The model writes Markdown (headings, lists, tables, bold), the format it writes
best, and the server converts it, so the web chat and the mobile app still get
HTML. Raw HTML in the model's text is escaped, never passed through: a web page
the assistant read cannot make it put markup or scripts into the chat.

While the answer streams, Stream hands out each finished block (a paragraph,
list or table, ended by a blank line) as HTML at once, and keeps the block
being written as plain text for the live preview.
"""

import re

import mistune

_render = mistune.create_markdown(escape=True, plugins=["table", "strikethrough"])

FENCE = re.compile(r"^```", re.MULTILINE)


def to_html(text):
    return _render(str(text or "")).strip()


# A table's rule line ("| :--- | ---: |"), whole or still being written.
TABLE_RULE = re.compile(r"^[ \t]*\|?[ \t:|-]*-[ \t:|-]*$", re.MULTILINE)


def plain(text):
    """Markdown as readable text, for the live preview of the block being written.

    A table being written reads as its cells ("Country · Value · Period"), not as pipes and dashes.
    """
    text = TABLE_RULE.sub("", str(text or ""))
    text = re.sub(r"^[ \t]*\|[ \t]*|[ \t]*\|[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*", " · ", text)
    text = re.sub(r"^\s{0,3}(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s?)", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Stream:
    """Finished blocks as HTML while the Markdown streams in."""

    def __init__(self):
        self.buffer = ""

    def _split(self):
        """Where the finished blocks end (after the last blank line outside a code fence), or -1."""
        end = self.buffer.rfind("\n\n")
        if end == -1:
            return -1
        # An odd number of fences before it: that blank line is inside a code block.
        return -1 if len(FENCE.findall(self.buffer[:end])) % 2 else end + 2

    def feed(self, piece):
        """(HTML of the blocks finished now, the block still being written)."""
        self.buffer += str(piece or "")
        end = self._split()
        if end == -1:
            return "", self.buffer
        done, self.buffer = self.buffer[:end], self.buffer[end:]
        return to_html(done), self.buffer

    def flush(self):
        """HTML of what is left once the writer is done."""
        text, self.buffer = self.buffer, ""
        return to_html(text)
