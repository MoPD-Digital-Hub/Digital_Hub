"""PowerPoint: 16:9 slides in the Ministry's design, with native (editable) charts."""

import io

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from ai.documents import charts, design

WIDTH, HEIGHT = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
MAX_TABLE_ROWS = 10


def _colour(hex_colour):
    return RGBColor.from_string(hex_colour)


class Deck:
    def __init__(self, language):
        self.language = language
        self.font = design.ui_font(language)
        self.words = design.words(language)
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = WIDTH, HEIGHT
        self.blank = self.prs.slide_layouts[6]
        self.count = 0

    # -- building blocks --------------------------------------------------

    def slide(self, notes=""):
        slide = self.prs.slides.add_slide(self.blank)
        self.count += 1
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        return slide

    def box(self, slide, left, top, width, height, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE):
        shape = slide.shapes.add_shape(shape, left, top, width, height)
        if fill:
            shape.fill.solid()
            shape.fill.fore_color.rgb = _colour(fill)
        else:
            shape.fill.background()
        if line:
            shape.line.color.rgb = _colour(line)
            shape.line.width = Pt(0.75)
        else:
            shape.line.fill.background()
        shape.shadow.inherit = False
        return shape

    def text(self, slide, left, top, width, height, text, size=18, colour=design.INK, bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
        frame = slide.shapes.add_textbox(left, top, width, height).text_frame
        frame.word_wrap = True
        frame.vertical_anchor = anchor
        frame.margin_left = frame.margin_right = Inches(0.05)
        paragraph = frame.paragraphs[0]
        paragraph.alignment = align
        self._run(paragraph, text, size, colour, bold)
        return frame

    def _run(self, paragraph, text, size, colour, bold=False):
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = self.font
        run.font.color.rgb = _colour(colour)
        return run

    def bullets(self, slide, left, top, width, height, points, size=17):
        frame = slide.shapes.add_textbox(left, top, width, height).text_frame
        frame.word_wrap = True
        for i, point in enumerate(points):
            paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            paragraph.space_after = Pt(12)
            paragraph.line_spacing = 1.1
            self._run(paragraph, "▪  ", size - 2, design.TEAL, bold=True)
            self._run(paragraph, point, size, design.INK)
        return frame

    def header(self, slide, title):
        self.box(slide, 0, 0, WIDTH, Inches(0.12), fill=design.TEAL)
        self.box(slide, MARGIN, Inches(0.55), Inches(0.09), Inches(0.62), fill=design.TEAL)
        self.text(slide, MARGIN + Inches(0.25), Inches(0.45), WIDTH - 2 * MARGIN, Inches(0.85), title, size=28,
                  bold=True, anchor=MSO_ANCHOR.MIDDLE)

    def footer(self, slide, source=""):
        top = HEIGHT - Inches(0.5)
        self.box(slide, MARGIN, top - Inches(0.08), WIDTH - 2 * MARGIN, Emu(9525), fill=design.LINE)
        if source:
            self.text(slide, MARGIN, top, Inches(9.6), Inches(0.35), source, size=10, colour=design.MUTED)
        self.text(slide, WIDTH - MARGIN - Inches(2.6), top, Inches(2.6), Inches(0.35),
                  f"{self.words['ministry']}  ·  {self.count}", size=10, colour=design.MUTED, align=PP_ALIGN.RIGHT)

    # -- visuals --------------------------------------------------------------

    def chart(self, slide, left, top, width, height, chart):
        lines = charts.series_of(chart)
        labels = []
        for _, line_labels, _ in lines:
            labels += [label for label in line_labels if label not in labels]
        data = CategoryChartData()
        data.categories = labels
        for name, line_labels, values in lines:
            by_label = dict(zip(line_labels, values))
            data.add_series(name or chart.get("label") or "", [
                by_label.get(label) if isinstance(by_label.get(label), (int, float)) else None for label in labels])
        if chart.get("type") == "bar":
            kind = XL_CHART_TYPE.BAR_CLUSTERED if len(labels) > 6 else XL_CHART_TYPE.COLUMN_CLUSTERED
        else:
            kind = XL_CHART_TYPE.LINE_MARKERS
        graphic = slide.shapes.add_chart(kind, left, top, width, height, data).chart
        graphic.has_title = False  # the dataset title sits above the chart
        graphic.font.size = Pt(11)
        graphic.font.name = self.font
        graphic.font.color.rgb = _colour(design.MUTED)
        graphic.has_legend = len(lines) > 1
        if graphic.has_legend:
            graphic.legend.position = XL_LEGEND_POSITION.TOP
            graphic.legend.include_in_layout = False
        for i, series in enumerate(graphic.series):
            colour = _colour(design.SERIES_COLOURS[i % len(design.SERIES_COLOURS)])
            if kind == XL_CHART_TYPE.LINE_MARKERS:
                series.format.line.color.rgb = colour
                series.format.line.width = Pt(2.5)
                series.smooth = False
                series.marker.format.fill.solid()
                series.marker.format.fill.fore_color.rgb = colour
                series.marker.format.line.color.rgb = colour
            else:
                series.format.fill.solid()
                series.format.fill.fore_color.rgb = colour
        if kind == XL_CHART_TYPE.BAR_CLUSTERED:
            graphic.category_axis.reverse_order = True
            graphic.plots[0].has_data_labels = True
            graphic.plots[0].data_labels.font.size = Pt(10)
        value_axis = graphic.value_axis
        value_axis.has_major_gridlines = True
        value_axis.major_gridlines.format.line.color.rgb = _colour(design.LINE)
        value_axis.format.line.fill.background()
        if chart.get("label"):
            value_axis.has_title = True
            value_axis.axis_title.text_frame.text = chart["label"]
            title_run = value_axis.axis_title.text_frame.paragraphs[0].runs[0]
            title_run.font.size = Pt(10)
            title_run.font.bold = False
            title_run.font.name = self.font
        return graphic

    def table(self, slide, left, top, width, table):
        headers, rows = table["headers"], table["rows"][:MAX_TABLE_ROWS]
        row_height = Inches(0.42)
        shape = slide.shapes.add_table(len(rows) + 1, len(headers), left, top, width, row_height * (len(rows) + 1))
        grid = shape.table
        for c, header in enumerate(headers):
            self._cell(grid.cell(0, c), header, header=True)
        for r, row in enumerate(rows, start=1):
            for c in range(len(headers)):
                self._cell(grid.cell(r, c), row[c] if c < len(row) else "", shaded=r % 2 == 0)
        return grid

    def _cell(self, cell, value, header=False, shaded=False):
        cell.fill.solid()
        cell.fill.fore_color.rgb = _colour(design.TEAL if header else (design.TEAL_LIGHT if shaded else "FFFFFF"))
        frame = cell.text_frame
        frame.text = ""
        cell.margin_left = cell.margin_right = Inches(0.08)
        self._run(frame.paragraphs[0], str(value), 12, "FFFFFF" if header else design.INK, bold=header)

    # -- slides ----------------------------------------------------------------

    def title_slide(self, outline):
        slide = self.slide()
        self.box(slide, 0, 0, WIDTH, HEIGHT, fill=design.TEAL_DARK)
        self.box(slide, 0, 0, Inches(0.35), HEIGHT, fill=design.TEAL)
        if design.LOGO.exists():
            tile = self.box(slide, MARGIN + Inches(0.3), Inches(0.65), Inches(1.15), Inches(1.15), fill="FFFFFF",
                            shape=MSO_SHAPE.ROUNDED_RECTANGLE)
            tile.adjustments[0] = 0.18
            slide.shapes.add_picture(str(design.LOGO), MARGIN + Inches(0.42), Inches(0.77), height=Inches(0.91))
        self.text(slide, MARGIN + Inches(0.3), Inches(2.3), Inches(11.4), Inches(2.2), outline["title"], size=44,
                  colour="FFFFFF", bold=True, anchor=MSO_ANCHOR.BOTTOM)
        if outline["subtitle"]:
            self.text(slide, MARGIN + Inches(0.3), Inches(4.65), Inches(11.4), Inches(1.0), outline["subtitle"],
                      size=20, colour="CFE7E3")
        self.box(slide, MARGIN + Inches(0.3), Inches(5.9), Inches(1.2), Inches(0.06), fill=design.AMBER)
        self.text(slide, MARGIN + Inches(0.3), Inches(6.1), Inches(11), Inches(0.5),
                  f"{self.words['ministry']}  ·  {design.today()}", size=14, colour="CFE7E3")

    def messages_slide(self, title, messages, notes=""):
        slide = self.slide(notes)
        self.header(slide, title)
        count = max(len(messages), 1)
        gap = Inches(0.3)
        card_width = int((WIDTH - 2 * MARGIN - gap * (count - 1)) / count)
        for i, message in enumerate(messages):
            left = MARGIN + i * (card_width + gap)
            self.box(slide, left, Inches(2.05), card_width, Inches(3.2), fill=design.TEAL_LIGHT)
            self.box(slide, left, Inches(2.05), card_width, Inches(0.09), fill=design.TEAL)
            self.text(slide, left + Inches(0.35), Inches(2.3), card_width - Inches(0.7), Inches(2.8), message,
                      size=24 if count <= 3 else 20, colour=design.INK, anchor=MSO_ANCHOR.MIDDLE)
        self.footer(slide)

    def section_slide(self, section, dataset):
        slide = self.slide(section["notes"])
        self.header(slide, section["heading"])
        top, height = Inches(1.65), Inches(5.0)
        if dataset is None:
            self.bullets(slide, MARGIN + Inches(0.2), top, WIDTH - 2 * MARGIN - Inches(0.4), height, section["points"],
                         size=20)
            self.footer(slide)
            return
        text_width = Inches(4.9) if section["points"] else 0
        if section["points"]:
            self.bullets(slide, MARGIN + Inches(0.1), top, text_width - Inches(0.2), height, section["points"])
        visual_left = MARGIN + text_width + (Inches(0.3) if section["points"] else 0)
        visual_width = WIDTH - MARGIN - visual_left
        self.text(slide, visual_left, top - Inches(0.05), visual_width, Inches(0.4), dataset["title"], size=13,
                  colour=design.MUTED, bold=True)
        if section["visual"] == "chart" and dataset.get("chart"):
            self.chart(slide, visual_left, top + Inches(0.4), visual_width, height - Inches(0.6), dataset["chart"])
        elif dataset.get("table"):
            self.table(slide, visual_left, top + Inches(0.45), visual_width, dataset["table"])
        self.footer(slide, dataset.get("source", ""))

    def sources_slide(self, sources):
        slide = self.slide()
        self.header(slide, self.words["sources"])
        self.bullets(slide, MARGIN + Inches(0.2), Inches(1.7), WIDTH - 2 * MARGIN, Inches(4.2), sources or ["—"],
                     size=16)
        self.text(slide, MARGIN + Inches(0.2), Inches(6.05), WIDTH - 2 * MARGIN, Inches(0.6),
                  self.words["prepared"].format(date=design.today()), size=12, colour=design.MUTED)
        self.footer(slide)


def build(outline, datasets, sources, language):
    """(bytes, number of slides)."""
    deck = Deck(language)
    deck.title_slide(outline)
    if outline["key_messages"]:
        deck.messages_slide(deck.words["key_messages"], outline["key_messages"])
    for section in outline["sections"]:
        dataset = datasets[section["dataset"]] if section["dataset"] is not None else None
        deck.section_slide(section, dataset)
    if outline["conclusion"]:
        deck.messages_slide(deck.words["conclusion"], outline["conclusion"])
    deck.sources_slide(sources)
    buffer = io.BytesIO()
    deck.prs.save(buffer)
    return buffer.getvalue(), deck.count
