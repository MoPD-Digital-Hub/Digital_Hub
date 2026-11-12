import io
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ai.documents import datasets, design, outline, pdf, service, slides, word
from ai.engine import planner
from ai.models import AnswerTrace, ChatInstance, GeneratedDocument

DATASETS = [
    {"title": "GDP Growth: annual", "source": "Source: MoPD",
     "chart": {"type": "line", "label": "GDP Growth (%)", "labels": ["2016", "2017", "2018"], "data": [8.05, 9.2, 7.7]},
     "table": {"headers": ["Period", "Value (%)"], "rows": [["2016", "8.05"], ["2017", "9.2"], ["2018", "7.7"]]}},
    {"title": "Ministries: score, 2017 EC", "source": "Source: DPMES", "chart": None,
     "table": {"headers": ["#", "Name", "Score (%)"], "rows": [["1", "Ministry of Revenue", "98.35"]]}},
]


def sample_outline(title="GDP growth 2016–2018 EC"):
    return {
        "title": title, "subtitle": "Official figures", "key_messages": ["GDP grew 9.2% in 2017 EC."],
        "sections": [
            {"heading": "Trend", "points": ["Growth rose to 9.2%."], "visual": "chart", "dataset": 0, "notes": "n"},
            {"heading": "Ministries", "points": ["Revenue led."], "visual": "table", "dataset": 1, "notes": ""},
            {"heading": "Context", "points": ["Broad-based."], "visual": "none", "dataset": None, "notes": ""},
        ],
        "conclusion": ["Sustain reforms."], "min_sections": 3,
    }


def plain_outline():
    """An outline without figures or charts, for runs that fetch no data."""
    return {"title": "Growth brief", "subtitle": "", "key_messages": ["Growth stayed positive."],
            "sections": [{"heading": "Context", "points": ["Growth was broad-based."], "visual": "none",
                          "dataset": None, "notes": ""}],
            "conclusion": ["Sustain reforms."], "min_sections": 3}


class DatasetTests(SimpleTestCase):
    def test_chat_blocks_become_datasets(self):
        parts = ['<h4>GDP Growth: annual</h4>',
                 '<table><thead><tr><th>Period</th><th>Value (%)</th></tr></thead>'
                 '<tbody><tr><td>2017</td><td><span style="color:red">9.2</span></td></tr></tbody></table>',
                 '<chart-data>{"type": "line", "label": "GDP Growth (%)", "labels": ["2017"], "data": [9.2]}</chart-data>']
        with patch.dict(datasets.render.RENDERERS, {"indicator_series": lambda result: parts}), \
                patch.object(datasets.render, "_source", return_value='<p class="ai-source">Source: MoPD</p>'):
            built = datasets.build([{"tool": "indicator_series"}, {"tool": "unknown"}])
        self.assertEqual(len(built), 1)
        self.assertEqual(built[0]["title"], "GDP Growth: annual")
        self.assertEqual(built[0]["table"], {"headers": ["Period", "Value (%)"], "rows": [["2017", "9.2"]]})
        self.assertEqual(built[0]["chart"]["data"], [9.2])
        self.assertEqual(built[0]["source"], "Source: MoPD")
        self.assertEqual(datasets.sources(built, [{"title": "IMF", "url": "https://imf.org"}]),
                         ["MoPD", "IMF (https://imf.org)"])


class OutlineTests(SimpleTestCase):
    def test_list_numbers_are_removed_but_figures_kept(self):
        raw = {"title": "T", "key_messages": ["10.41% was the peak.", "1. Growth slowed.", "- 7.7% in 2018."],
               "sections": [], "conclusion": []}
        cleaned = outline._clean(raw, [], "pptx")
        self.assertEqual(cleaned["key_messages"], ["10.41% was the peak.", "Growth slowed.", "7.7% in 2018."])

    def test_visuals_point_at_real_datasets_once_and_none_is_left_out(self):
        raw = {"title": "T", "key_messages": [], "conclusion": [], "sections": [
            {"heading": "A", "points": ["p"], "visual": "chart", "dataset": 1},   # dataset 1 has no chart: table
            {"heading": "B", "points": ["p"], "visual": "chart", "dataset": 1},   # already used
            {"heading": "C", "points": ["p"], "visual": "table", "dataset": 9},   # no such dataset
        ]}
        sections = outline._clean(raw, DATASETS, "pptx")["sections"]
        self.assertEqual([(s["visual"], s["dataset"]) for s in sections],
                         [("table", 1), ("none", None), ("none", None), ("chart", 0)])
        self.assertEqual(sections[3]["heading"], "GDP Growth: annual")

    def test_the_writer_is_told_which_numbers_to_drop(self):
        messages = outline.messages("PPT on GDP", "pptx", "English", DATASETS, [], [], avoid=[10.0, 93.0])
        self.assertIn("not in the facts: 10, 93", messages[1]["content"])
        self.assertIn('"dataset":0', messages[1]["content"])


class BuilderTests(SimpleTestCase):
    def test_every_format_builds_in_both_languages(self):
        from docx import Document
        from pptx import Presentation

        for language in ("English", "Amharic"):
            title = "የኢኮኖሚ ዕድገት 2018 ዓ.ም" if language == "Amharic" else "GDP growth"
            data, count = slides.build(sample_outline(title), DATASETS, ["MoPD"], language)
            deck = Presentation(io.BytesIO(data))
            self.assertEqual(len(deck.slides), count)
            self.assertEqual(count, 7)  # title, key messages, 3 sections, conclusion, sources
            self.assertTrue(any(shape.has_chart for shape in deck.slides[2].shapes))
            data, _ = word.build(sample_outline(title), DATASETS, ["MoPD"], language)
            self.assertIn(title, "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs))
            data, pages = pdf.build(sample_outline(title), DATASETS, ["MoPD"], language)
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertGreaterEqual(pages, 1)
            self.assertLess(len(data), 1_000_000)

    def test_ethiopic_runs_get_the_ethiopic_font_and_punctuation_the_latin_one(self):
        self.assertEqual(pdf.markup("ዓ.ም (GDP)"),
                         '<font name="NotoSansEthiopic">ዓ</font><font name="NotoSans">.</font>'
                         '<font name="NotoSansEthiopic">ም </font><font name="NotoSans">(GDP)</font>')

    def test_file_names_keep_amharic_and_dots(self):
        self.assertEqual(design.safe_filename("ሪፖርት 2018 ዓ.ም: GDP/Growth?", "pdf"), "ሪፖርት 2018 ዓ.ም GDPGrowth.pdf")


@override_settings(AI_DOCUMENT_DAYS=7, SITE_URL="https://hub.example")
class DownloadTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="o", email="o@x.test", password="p")
        self.other = users.create_user(username="x", email="x@x.test", password="p")
        chat = ChatInstance.objects.create(title="t", user=self.owner)
        self.document = async_to_sync(service.save)(chat, "pdf", "GDP report", b"%PDF-1.4 test")

    def url(self, token=None):
        path = reverse("ai-document", args=[self.document.id])
        return path + (f"?t={token}" if token is not None else "")

    def test_the_signed_link_downloads_without_a_session(self):
        link = service.download_url(self.document)
        self.assertTrue(link.startswith(f"https://hub.example/api/ai-chat/documents/{self.document.id}/?t="))
        response = self.client.get(self.url(service.token(self.document.id)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("GDP%20report.pdf", response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 test")

    def test_the_owner_needs_no_token_and_others_need_one(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.get(self.url(service.token("another-id"))).status_code, 404)

    def test_expired_files_are_gone_and_deleted_by_the_cleanup(self):
        GeneratedDocument.objects.filter(id=self.document.id).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(self.url(service.token(self.document.id))).status_code, 410)
        self.assertEqual(service.delete_expired(), 1)
        self.assertFalse(GeneratedDocument.objects.exists())


class PlannerTests(SimpleTestCase):
    def plan(self, raw, question="Make a PowerPoint on how ministries performed in 2017"):
        with patch("ai.engine.planner.llm.json_completion", AsyncMock(return_value=raw)):
            return async_to_sync(planner.plan)(question)

    def test_a_document_request_keeps_its_format_and_the_year(self):
        plan = self.plan({"kind": "document", "document_format": "pdf",
                          "calls": [{"tool": "rank_organizations", "order": "top"}]})
        self.assertEqual((plan.kind, plan.document_format), ("document", "pdf"))
        self.assertEqual(plan.calls, [{"tool": "rank_organizations", "order": "top", "year": 2017}])

    def test_the_format_defaults_to_powerpoint(self):
        self.assertEqual(self.plan({"kind": "document", "calls": []}).document_format, "pptx")

    def test_two_years_are_left_to_the_model(self):
        plan = self.plan({"kind": "data", "calls": [{"tool": "indicator_series", "indicator": "GDP"}]},
                         "GDP growth from 2010 to 2015")
        self.assertNotIn("year", plan.calls[0])


@override_settings(AI_DOCUMENTS_DAILY_LIMIT=5, SITE_URL="")
class PipelineTests(TestCase):
    def run_pipeline(self, outlines, instance=None):
        from ai.engine.pipeline import answer

        plan = planner.Plan("document", "English", [], document_format="pdf")
        write = AsyncMock(side_effect=outlines)
        with patch("ai.engine.pipeline.planner.plan", AsyncMock(return_value=plan)), \
                patch("ai.documents.outline.write", write):
            return async_to_sync(answer)("Make a PDF about growth", instance=instance), write

    def test_the_answer_announces_the_file_with_its_link(self):
        result, _ = self.run_pipeline([plain_outline()])
        document = GeneratedDocument.objects.get()
        self.assertEqual((document.format, document.title), ("pdf", "Growth brief"))
        self.assertTrue(bytes(document.content).startswith(b"%PDF"))
        self.assertIn("Your PDF report <b>Growth brief</b> is ready", result["answer"])
        self.assertIn(f'<p class="ai-document" data-format="pdf"><a href="/api/ai-chat/documents/{document.id}/?t=',
                      result["answer"])
        entry = [c for c in AnswerTrace.objects.get().tool_calls if c["tool"] == "document"][0]
        self.assertEqual(entry["id"], str(document.id))

    def test_unsupported_numbers_get_one_rewrite(self):
        first = plain_outline()
        first["key_messages"] = ["Growth reached 41% at its peak."]
        result, write = self.run_pipeline([first, plain_outline()])
        self.assertEqual(write.await_count, 2)
        self.assertEqual(write.await_args.kwargs["avoid"], [41.0])
        self.assertEqual(AnswerTrace.objects.get().unsupported_numbers, [])

    @override_settings(AI_DOCUMENTS_DAILY_LIMIT=1)
    def test_the_daily_limit_stops_new_documents(self):
        user = get_user_model().objects.create_user(username="u", email="u@x.test", password="p")
        chat = ChatInstance.objects.create(title="t", user=user)
        async_to_sync(service.save)(chat, "pdf", "earlier", b"%PDF")
        result, write = self.run_pipeline([plain_outline()], instance=chat)
        write.assert_not_called()
        self.assertIn("today's limit for documents", result["answer"])
