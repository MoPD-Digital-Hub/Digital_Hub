"""PDF: an A4 report in the Ministry's design, with the Noto fonts embedded (Ethiopic included)."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai.documents import charts, design

MAX_TABLE_ROWS = 25
_FONTS_READY = False
LATIN, LATIN_BOLD, ETHIOPIC, ETHIOPIC_BOLD = "NotoSans", "NotoSans-Bold", "NotoSansEthiopic", "NotoSansEthiopic-Bold"


def _fonts():
    global _FONTS_READY
    if not _FONTS_READY:
        for name, file in ((LATIN, "NotoSans-Regular.ttf"), (LATIN_BOLD, "NotoSans-Bold.ttf"),
                           (ETHIOPIC, "NotoSansEthiopic-Regular.ttf"), (ETHIOPIC_BOLD, "NotoSansEthiopic-Bold.ttf")):
            pdfmetrics.registerFont(TTFont(name, str(design.FONTS_DIR / file)))
        pdfmetrics.registerFontFamily(LATIN, normal=LATIN, bold=LATIN_BOLD, italic=LATIN, boldItalic=LATIN_BOLD)
        pdfmetrics.registerFontFamily(ETHIOPIC, normal=ETHIOPIC, bold=ETHIOPIC_BOLD, italic=ETHIOPIC,
                                      boldItalic=ETHIOPIC_BOLD)
        _FONTS_READY = True


def markup(text, bold=False):
    """Paragraph markup with Ethiopic stretches in the Ethiopic font (reportlab has no per-glyph fallback)."""
    text = str(text or "")
    pieces, current, ethiopic = [], "", None
    for char in text:
        is_ethiopic = bool(design.ETHIOPIC.match(char))
        # Spaces stay with the run they are in; everything that is not Ethiopic
        # (Latin, digits, "." "(" "%") needs the Latin font, which has those glyphs.
        if char.isspace():
            current += char
            continue
        if ethiopic is None:
            ethiopic = is_ethiopic
        if is_ethiopic != ethiopic:
            pieces.append((ethiopic, current))
            current, ethiopic = "", is_ethiopic
        current += char
    if current:
        pieces.append((bool(ethiopic), current))
    out = []
    for is_ethiopic, piece in pieces:
        font = (ETHIOPIC_BOLD if bold else ETHIOPIC) if is_ethiopic else (LATIN_BOLD if bold else LATIN)
        out.append(f'<font name="{font}">{escape(piece)}</font>')
    return "".join(out)


def _colour(hex_colour):
    return colors.HexColor("#" + hex_colour)


STYLES = {
    "ministry": dict(fontSize=9, textColor=design.TEAL, leading=12, spaceAfter=14),
    "title": dict(fontSize=24, textColor=design.TEAL_DARK, leading=30, spaceAfter=8),
    "subtitle": dict(fontSize=12.5, textColor=design.MUTED, leading=17, spaceAfter=4),
    "date": dict(fontSize=9.5, textColor=design.MUTED, leading=13, spaceAfter=18),
    "h1": dict(fontSize=15, textColor=design.TEAL_DARK, leading=20, spaceBefore=16, spaceAfter=6),
    "h2": dict(fontSize=11.5, textColor=design.MUTED, leading=15, spaceBefore=8, spaceAfter=6),
    "body": dict(fontSize=10.5, textColor=design.INK, leading=15.5, spaceAfter=4),
    "cell": dict(fontSize=9, textColor=design.INK, leading=12),
    "head_cell": dict(fontSize=9, textColor="FFFFFF", leading=12),
    "small": dict(fontSize=8.5, textColor=design.MUTED, leading=12, spaceAfter=10),
}


def _style(name):
    values = dict(STYLES[name])
    values["textColor"] = _colour(values["textColor"])
    return ParagraphStyle(name, fontName=LATIN, alignment=TA_LEFT, **values)


class Report:
    def __init__(self, language):
        _fonts()
        self.language = language
        self.words = design.words(language)
        self.story = []
        self.styles = {name: _style(name) for name in STYLES}

    def p(self, text, style="body", bold=False):
        self.story.append(Paragraph(markup(text, bold), self.styles[style]))

    def bullets(self, points, style="body"):
        items = [ListItem(Paragraph(markup(point), self.styles[style]), leftIndent=12, value="•")
                 for point in points]
        self.story.append(ListFlowable(items, bulletType="bullet", bulletColor=_colour(design.TEAL), leftIndent=14,
                                       bulletFontSize=9))

    def cover(self, outline):
        if design.LOGO.exists():
            logo = Image(str(design.LOGO), width=1.6 * cm, height=1.6 * cm, kind="proportional")
            logo.hAlign = "LEFT"
            self.story.append(logo)
            self.story.append(Spacer(1, 6))
        self.p(self.words["ministry"].upper() if self.language == "English" else self.words["ministry"], "ministry",
               bold=True)
        self.p(outline["title"], "title", bold=True)
        if outline["subtitle"]:
            self.p(outline["subtitle"], "subtitle")
        self.p(design.today(), "date")

    def callout(self, title, items):
        inner = [Paragraph(markup(title, bold=True), self.styles["h2"])]
        inner += [Paragraph(markup("•  " + item), self.styles["body"]) for item in items]
        box = Table([[inner]], colWidths=[16.6 * cm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _colour(design.TEAL_LIGHT)),
            ("LINEBEFORE", (0, 0), (0, -1), 3, _colour(design.TEAL)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        self.story.append(box)
        self.story.append(Spacer(1, 10))

    def chart(self, chart):
        image = Image(io.BytesIO(charts.png(chart)), width=16.6 * cm, height=16.6 * cm * 3.1 / 6.6)
        self.story.append(image)

    def table(self, table):
        headers, rows = table["headers"], table["rows"][:MAX_TABLE_ROWS]
        data = [[Paragraph(markup(h, bold=True), self.styles["head_cell"]) for h in headers]]
        data += [[Paragraph(markup(row[c] if c < len(row) else ""), self.styles["cell"]) for c in range(len(headers))]
                 for row in rows]
        grid = Table(data, repeatRows=1, colWidths=[16.6 * cm * share for share in design.column_shares(headers, rows)])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _colour(design.TEAL)),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, _colour(design.LINE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        style += [("BACKGROUND", (0, r), (-1, r), _colour(design.TEAL_LIGHT)) for r in range(2, len(data), 2)]
        grid.setStyle(TableStyle(style))
        self.story.append(grid)
        self.story.append(Spacer(1, 6))

    def section(self, section, dataset):
        block = [Paragraph(markup(section["heading"], bold=True), self.styles["h1"])]
        self.story.append(KeepTogether(block))
        if section["points"]:
            self.bullets(section["points"])
        if dataset is None:
            return
        self.p(dataset["title"], "h2", bold=True)
        if section["visual"] == "chart" and dataset.get("chart"):
            self.chart(dataset["chart"])
        elif dataset.get("table"):
            self.table(dataset["table"])
        if dataset.get("source"):
            self.p(dataset["source"], "small")


def _page_decoration(words):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(_colour(design.TEAL))
        canvas.rect(0, height - 0.35 * cm, width, 0.35 * cm, stroke=0, fill=1)
        canvas.setFillColor(_colour(design.MUTED))
        canvas.setFont(LATIN, 8)
        ministry = words["ministry"]
        font = ETHIOPIC if design.ETHIOPIC.search(ministry) else LATIN
        canvas.setFont(font, 8)
        canvas.drawString(2.2 * cm, 1.2 * cm, ministry)
        canvas.setFont(LATIN, 8)
        canvas.drawRightString(width - 2.2 * cm, 1.2 * cm, str(doc.page))
        canvas.restoreState()
    return draw


def build(outline, datasets, sources, language):
    """(bytes, number of pages)."""
    report = Report(language)
    report.cover(outline)
    if outline["key_messages"]:
        report.callout(report.words["key_messages"], outline["key_messages"])
    for section in outline["sections"]:
        report.section(section, datasets[section["dataset"]] if section["dataset"] is not None else None)
    if outline["conclusion"]:
        report.p(report.words["conclusion"], "h1", bold=True)
        report.bullets(outline["conclusion"])
    report.p(report.words["sources"], "h1", bold=True)
    report.bullets(sources or ["—"])
    report.p(report.words["prepared"].format(date=design.today()), "small")

    buffer = io.BytesIO()
    pages = []
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                                 topMargin=2.0 * cm, bottomMargin=2.0 * cm, title=outline["title"],
                                 author=design.words("English")["ministry"])
    decorate = _page_decoration(report.words)

    def on_page(canvas, doc):
        decorate(canvas, doc)
        pages.append(doc.page)

    document.build(report.story, onFirstPage=on_page, onLaterPages=on_page)
    return buffer.getvalue(), len(pages)
