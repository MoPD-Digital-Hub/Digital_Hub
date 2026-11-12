"""Web search for Admas AI's general questions, and reading the pages found.

Searches go to the Digital Hub's own SearXNG (SEARXNG_URL; the `searxng`
service in compose.yaml and deploy/compose.production.yaml), which asks public
search engines and returns their results as JSON. Only the short query leaves
the server, never the chat or the user.

Never used for Ethiopia's official figures: those come from the time-series
service, DPMES and the SDG platform.

Pages are fetched only from public internet addresses (a result, or a
redirect, can never make the server fetch something on its own network), and
are read as plain text.
"""

import hashlib
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.cache import cache

SEARCH_TIMEOUT_SECONDS = 15
PAGE_TIMEOUT_SECONDS = 8
CACHE_SECONDS = 30 * 60
MAX_PAGE_BYTES = 1_500_000
MAX_REDIRECTS = 3
USER_AGENT = "Mozilla/5.0 (compatible; DigitalHub/1.0; +https://data-hub.mopd.gov.et)"

# Official, international and established sources rank first.
PREFERRED_SITES = (
    "gov.et", "un.org", "worldbank.org", "imf.org", "who.int", "afdb.org", "unicef.org", "undp.org", "fao.org",
    "wfp.org", "ilo.org", "unesco.org", "oecd.org", "au.int", "uneca.org", "ifad.org", "unhcr.org", "unfpa.org",
    "ena.et", "nbe.gov.et", "wikipedia.org", "britannica.com", "reuters.com", "apnews.com", "bbc.com",
    "bbc.co.uk", "aljazeera.com", "theguardian.com", "ft.com", "economist.com", "addisstandard.com",
    "thereporterethiopia.com", "addisfortune.news", "fanamc.com",
)
# Social media, video and forums: little readable text, or no editorial standard.
BLOCKED_SITES = (
    "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "youtube.com", "youtu.be",
    "pinterest.com", "reddit.com", "quora.com", "linkedin.com", "t.me", "telegram.me",
)


class WebSearchError(Exception):
    """The search service could not be reached or gave no usable answer."""


def enabled():
    return bool(settings.SEARXNG_URL) and settings.WEB_SEARCH_ENABLED


def site_of(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(site, domains):
    return any(site == domain or site.endswith("." + domain) for domain in domains)


def _rank(index, site):
    """Lower is better: the engines' order, with trusted sites lifted."""
    return index - (8 if _matches(site, PREFERRED_SITES) else 0)


def search(query, limit=6):
    """Up to `limit` results: [{"title", "url", "site", "snippet", "published"}], best first."""
    query = re.sub(r"\s+", " ", str(query or "")).strip()[:200]
    if not query:
        return []
    if not enabled():
        raise WebSearchError("web search is turned off")
    key = "websearch:" + hashlib.sha256(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached[:limit]
    try:
        response = requests.get(
            settings.SEARXNG_URL.rstrip("/") + "/search",
            params={"q": query, "format": "json", "safesearch": 1, "language": "en"},
            headers={"Accept": "application/json"},
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        raw = response.json().get("results") or []
    except (requests.RequestException, ValueError) as exc:
        raise WebSearchError(f"the search service is unavailable ({exc})") from exc

    seen, ranked = set(), []
    for index, item in enumerate(raw):
        url = str(item.get("url") or "")
        site = site_of(url)
        if urlparse(url).scheme not in ("http", "https") or not site or _matches(site, BLOCKED_SITES):
            continue
        if url in seen:
            continue
        seen.add(url)
        ranked.append((_rank(index, site), {
            "title": _clean(item.get("title"))[:200],
            "url": url,
            "site": site,
            "snippet": _clean(item.get("content"))[:500],
            "published": str(item.get("publishedDate") or "")[:10],
        }))
    results = [result for _, result in sorted(ranked, key=lambda pair: pair[0])]
    cache.set(key, results, CACHE_SECONDS)
    return results[:limit]


def _clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text or ""))).strip()


def is_public_host(host):
    """True when every address the host resolves to is on the public internet."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses)


def read_page(url, max_chars=3500):
    """The readable text of a public web page, or "" when it cannot be read."""
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or not is_public_host(parsed.hostname):
            return ""
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=PAGE_TIMEOUT_SECONDS,
                                    allow_redirects=False, stream=True)
        except requests.RequestException:
            return ""
        with response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            content_type = response.headers.get("Content-Type", "")
            if response.status_code != 200 or not re.match(r"text/(html|plain)", content_type):
                return ""
            body = b""
            try:
                for chunk in response.iter_content(65536):
                    body += chunk
                    if len(body) > MAX_PAGE_BYTES:
                        break
            except requests.RequestException:
                return ""
            text = body.decode(response.encoding or "utf-8", errors="replace")
        if content_type.startswith("text/plain"):
            return _clean(text)[:max_chars]
        return page_text(text)[:max_chars]
    return ""


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "iframe", "button",
            "select", "template"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article", "blockquote",
             "dd", "dt", "td", "th", "table", "ul", "ol", "main"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skipping = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def page_text(html, min_line_chars=40):
    """Readable text of an HTML page: its sentences, without menus, scripts and short fragments."""
    parser = _TextExtractor()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:  # malformed markup: keep what was read
        pass
    lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
    return "\n".join(line for line in lines if len(line) >= min_line_chars)
