import socket
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from integrations.websearch import client

SEARX = {"results": [
    {"url": "https://www.youtube.com/watch?v=1", "title": "Video", "content": "watch"},
    {"url": "https://someblog.example/imf-ethiopia", "title": "A blog", "content": "Blog <b>post</b>"},
    {"url": "https://www.imf.org/en/news/ethiopia", "title": "IMF and Ethiopia", "content": "Press release",
     "publishedDate": "2026-07-01T00:00:00"},
    {"url": "https://www.imf.org/en/news/ethiopia", "title": "Duplicate", "content": "again"},
    {"url": "ftp://files.example/x", "title": "FTP", "content": "file"},
]}


def json_response(payload, status=200):
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    response.raise_for_status.side_effect = None if status == 200 else requests.HTTPError(str(status))
    return response


def page_response(body, content_type="text/html; charset=utf-8", status=200, location=None):
    response = MagicMock(status_code=status, encoding="utf-8")
    response.is_redirect = location is not None
    response.headers = {"Content-Type": content_type, **({"Location": location} if location else {})}
    response.iter_content.return_value = [body.encode()]
    response.__enter__.return_value = response
    return response


def resolves_to(*addresses):
    return lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in addresses]


@override_settings(SEARXNG_URL="http://searxng:8080", WEB_SEARCH_ENABLED=True)
class SearchTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_results_are_filtered_deduplicated_and_trusted_sites_lifted(self):
        with patch.object(client.requests, "get", return_value=json_response(SEARX)) as get:
            results = client.search("  IMF   Ethiopia ")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "IMF Ethiopia")
        self.assertEqual(get.call_args.kwargs["params"]["format"], "json")
        self.assertEqual([r["site"] for r in results], ["imf.org", "someblog.example"])
        self.assertEqual(results[0]["published"], "2026-07-01")
        self.assertEqual(results[1]["snippet"], "Blog post")

    def test_results_are_cached(self):
        with patch.object(client.requests, "get", return_value=json_response(SEARX)) as get:
            client.search("IMF Ethiopia")
            client.search("imf ethiopia")
        self.assertEqual(get.call_count, 1)

    def test_an_unreachable_service_is_an_error(self):
        with patch.object(client.requests, "get", side_effect=requests.ConnectionError("refused")), \
                self.assertRaises(client.WebSearchError):
            client.search("IMF Ethiopia")

    @override_settings(SEARXNG_URL="")
    def test_search_is_off_without_a_service(self):
        self.assertFalse(client.enabled())
        with self.assertRaises(client.WebSearchError):
            client.search("IMF Ethiopia")

    @override_settings(WEB_SEARCH_ENABLED=False)
    def test_search_can_be_turned_off(self):
        self.assertFalse(client.enabled())


class PageTests(SimpleTestCase):
    HTML = """<html><head><title>t</title><style>body{color:red}</style><script>var tracking = 1;</script></head>
    <body><nav>Home | About | Contact us today for more information here</nav>
    <article><h1>Ethiopia completes its fifth review with the IMF programme</h1>
    <p>The IMF Executive Board completed the fifth review of Ethiopia's arrangement, releasing USD 262 million.</p>
    <p>Short line.</p></article><footer>Copyright notice and other footer text that is long enough</footer></body></html>"""

    def test_page_text_keeps_sentences_and_drops_menus_scripts_and_fragments(self):
        text = client.page_text(self.HTML)
        self.assertIn("releasing USD 262 million", text)
        self.assertIn("fifth review with the IMF programme", text)
        self.assertNotIn("tracking", text)
        self.assertNotIn("Contact us", text)
        self.assertNotIn("footer text", text)
        self.assertNotIn("Short line", text)

    def test_only_public_addresses_are_fetched(self):
        for address in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"):
            with self.subTest(address), patch.object(client.socket, "getaddrinfo", resolves_to(address)):
                self.assertFalse(client.is_public_host("internal.example"))
        with patch.object(client.socket, "getaddrinfo", resolves_to("93.184.216.34")):
            self.assertTrue(client.is_public_host("example.org"))

    def test_read_page_returns_text_from_a_public_page(self):
        with patch.object(client.socket, "getaddrinfo", resolves_to("93.184.216.34")), \
                patch.object(client.requests, "get", return_value=page_response(self.HTML)):
            self.assertIn("USD 262 million", client.read_page("https://www.imf.org/en/news"))

    def test_a_redirect_to_an_internal_address_is_not_followed(self):
        def lookup(host, port):
            return resolves_to("10.0.0.5" if host == "intranet.local" else "93.184.216.34")(host, port)

        redirect = page_response("", status=302, location="http://intranet.local/admin")
        with patch.object(client.socket, "getaddrinfo", lookup), \
                patch.object(client.requests, "get", return_value=redirect) as get:
            self.assertEqual(client.read_page("https://example.org/r"), "")
        self.assertEqual(get.call_count, 1)

    def test_non_html_or_failing_pages_give_no_text(self):
        with patch.object(client.socket, "getaddrinfo", resolves_to("93.184.216.34")):
            with patch.object(client.requests, "get", return_value=page_response("%PDF", "application/pdf")):
                self.assertEqual(client.read_page("https://example.org/a.pdf"), "")
            with patch.object(client.requests, "get", side_effect=requests.Timeout("slow")):
                self.assertEqual(client.read_page("https://example.org/slow"), "")
        self.assertEqual(client.read_page("file:///etc/passwd"), "")
