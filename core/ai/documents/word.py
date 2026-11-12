"""Word: an A4 report in the Ministry's design, with chart images and tables."""

import io

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ai.documents import charts, design

MAX_TABLE_ROWS = 25


def _rgb(hex_colour):
    return RGBColor.from_string(hex_colour)


def _font(run_or_style, name):
    """Set the font for Latin and Ethiopic text alike (Word picks the slot by script)."""
    run_or_style.font.name = name
    element = run_or_style.element if hasattr(run_or_style, "element") else run_or_style._element
    properties = element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.append(fonts)
    for slot in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(slot), name)


def _shade(cell, hex_colour):
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), hex_colour)
    properties.append(shading)


class Report:
    def __init__(self, language):
        self.language = language
        self.font = design.ui_font(language)
        self.words = design.words(language)
        self.doc = Document()
        section = self.doc.sections[0]
        section.page_height, section.page_width = Cm(29.7), Cm(21.0)
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin, section.bottom_margin = Cm(2.0), Cm(2.0)
        normal = self.doc.styles["Normal"]
        _font(normal, self.font)
        normal.font.size = Pt(11)
        normal.font.color.rgb = _rgb(design.INK)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.15
        for name, size in (("Heading 1", 16), ("Heading 2", 13)):
            style = self.doc.styles[name]
            _font(style, self.font)
            style.font.size = Pt(size)
            style.font.bold = True
            style.font.color.rgb = _rgb(design.TEAL_DARK)
            style.paragraph_format.space_before = Pt(16)
            style.paragraph_format.space_after = Pt(6)
        self._footer()

    def _footer(self):
        paragraph = self.doc.sections[0].footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = paragraph.add_run(f"{self.words['ministry']}  ·  {self.words['page']} ")
        run.font.size = Pt(9)
        run.font.color.rgb = _rgb(design.MUTED)
        for code in ("begin", None, "end"):
            if code is None:
                instruction = OxmlElement("w:instrText")
                instruction.set(qn("xml:space"), "preserve")
                instruction.text = "PAGE"
                element = instruction
            else:
                element = OxmlElement("w:fldChar")
                element.set(qn("w:fldCharType"), code)
            page = paragraph.add_run()
            page.font.size = Pt(9)
            page.font.color.rgb = _rgb(design.MUTED)
            page._r.append(element)

    def paragraph(self, text, size=11, colour=design.INK, bold=False, after=6, align=None):
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(after)
        if align is not None:
            paragraph.alignment = align
        run = paragraph.add_run(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = _rgb(colour)
        return paragraph

    def bullets(self, points):
        for point in points:
            paragraph = self.doc.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(4)
            paragraph.add_run(point)

    def cover(self, outline):
        if design.LOGO.exists():
            self.doc.add_picture(str(design.LOGO), height=Cm(1.6))
        self.paragraph(self.words["ministry"].upper() if self.language == "English" else self.words["ministry"],
                       size=10, colour=design.TEAL, bold=True, after=14)
        self.paragraph(outline["title"], size=24, colour=design.TEAL_DARK, bold=True, after=6)
        if outline["subtitle"]:
            self.paragraph(outline["subtitle"], size=13, colour=design.MUTED, after=4)
        self.paragraph(design.today(), size=10, colour=design.MUTED, after=14)

    def callout(self, title, items):
        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        _shade(cell, design.TEAL_LIGHT)
        heading = cell.paragraphs[0]
        run = heading.add_run(title)
        run.font.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = _rgb(design.TEAL_DARK)
        for item in items:
            paragraph = cell.add_paragraph(style="List Bullet")
            paragraph.add_run(item)
        self.doc.add_paragraph()

    def chart(self, chart):
        self.doc.add_picture(io.BytesIO(charts.png(chart)), width=Cm(16.4))

    def table(self, table):
        headers, rows = table["headers"], table["rows"][:MAX_TABLE_ROWS]
        grid = self.doc.add_table(rows=len(rows) + 1, cols=len(headers))
        grid.style = "Table Grid"
        grid.alignment = WD_TABLE_ALIGNMENT.CENTER
        grid.autofit = False
        for c, share in enumerate(design.column_shares(headers, rows)):
            for cell in grid.columns[c].cells:
                cell.width = Cm(16.6 * share)
        for c, header in enumerate(headers):
            cell = grid.cell(0, c)
            _shade(cell, design.TEAL)
            run = cell.paragraphs[0].add_run(header)
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = _rgb("FFFFFF")
        for r, row in enumerate(rows, start=1):
            for c in range(len(headers)):
                cell = grid.cell(r, c)
                if r % 2 == 0:
                    _shade(cell, design.TEAL_LIGHT)
                run = cell.paragraphs[0].add_run(row[c] if c < len(row) else "")
                run.font.size = Pt(10)

    def source(self, text):
        if text:
            self.paragraph(text, size=9, colour=design.MUTED, after=10)

    def section(self, section, dataset):
        self.doc.add_heading(section["heading"], level=1)
        self.bullets(section["points"])
        if dataset is None:
            return
        self.doc.add_heading(dataset["title"], level=2)
        if section["visual"] == "chart" and dataset.get("chart"):
            self.chart(dataset["chart"])
        elif dataset.get("table"):
            self.table(dataset["table"])
            self.doc.add_paragraph()
        self.source(dataset.get("source"))


def build(outline, datasets, sources, language):
    """(bytes, number of sections)."""
    report = Report(language)
    report.cover(outline)
    if outline["key_messages"]:
        report.callout(report.words["key_messages"], outline["key_messages"])
    for section in outline["sections"]:
        report.section(section, datasets[section["dataset"]] if section["dataset"] is not None else None)
    if outline["conclusion"]:
        report.doc.add_heading(report.words["conclusion"], level=1)
        report.bullets(outline["conclusion"])
    report.doc.add_heading(report.words["sources"], level=1)
    report.bullets(sources or ["—"])
    report.paragraph(report.words["prepared"].format(date=design.today()), size=9, colour=design.MUTED)
    buffer = io.BytesIO()
    report.doc.save(buffer)
    return buffer.getvalue(), len(outline["sections"])
