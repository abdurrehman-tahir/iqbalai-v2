"""Web search + fetch tools — SearXNG meta-search + HTML text extraction.

The locked web-search provider is self-hosted **SearXNG** (STACK_LOCK §Web-search),
reached via ``WEBSEARCH_URL``. These are the two primitives the Pattern-A exam-
framework research run composes (T-093, ARCH §7.12/§8.21):

- :func:`web_search` — query SearXNG's JSON API for candidate sources.
- :func:`web_fetch`  — fetch a page and reduce it to readable plain text.

HTTP goes through ``httpx`` (raw ``requests``/``urllib`` are forbidden, STACK_LOCK §9).
Text extraction uses the standard-library HTML parser — no new dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Tags whose text content is noise, not article body.
_SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "svg", "nav", "footer"})
# Cap fetched text so one huge page can't blow the LLM context / cost budget.
_MAX_FETCH_CHARS = 20_000
_HTTP_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class SearchResult:
    """A single SearXNG hit."""

    title: str
    url: str
    snippet: str


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style/chrome tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    @property
    def text(self) -> str:
        return " ".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text[:_MAX_FETCH_CHARS]


async def web_search(query: str, max_results: int = 15) -> list[SearchResult]:
    """Search the web via SearXNG's JSON API.

    Returns up to ``max_results`` hits (title/url/snippet). Network/HTTP errors
    propagate to the caller — the research task decides retry vs. fail (T-093).
    """
    settings = get_settings()
    base = settings.WEBSEARCH_URL.rstrip("/")
    params = {"q": query, "format": "json"}
    # Pin reliable engines — SearXNG's default general engines CAPTCHA/rate-limit
    # automated queries and silently return zero results (see WEBSEARCH_ENGINES).
    if settings.WEBSEARCH_ENGINES.strip():
        params["engines"] = settings.WEBSEARCH_ENGINES.strip()
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        response = await client.get(f"{base}/search", params=params)
        response.raise_for_status()
        payload = response.json()

    results: list[SearchResult] = []
    for item in payload.get("results", [])[:max_results]:
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        results.append(
            SearchResult(
                title=str(item.get("title", "")).strip()[:512],
                url=url[:2048],
                snippet=str(item.get("content", "")).strip(),
            )
        )
    logger.info("web_search_complete", query=query, result_count=len(results))
    return results


async def web_fetch(url: str) -> str:
    """Fetch ``url`` and return its readable plain text (truncated).

    Returns an empty string on any fetch/parse failure so one bad source does not
    abort a multi-source research run; the caller filters empties.
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "IqbalAI-Research/1.0"})
            response.raise_for_status()
            return _html_to_text(response.text)
    except (httpx.HTTPError, ValueError) as exc:
        # One unreachable/garbage page must not sink the whole run — skip it.
        logger.warning("web_fetch_failed", url=url, error=str(exc))
        return ""
