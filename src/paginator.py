"""Pagination support for fetching multi-page listings.

The Paginator follows "next page" links in HTML responses to exhaustively
fetch all pages of a paginated source.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from loguru import logger

from src.fetcher import fetch_html

# Regex for common "next" text indicators (e.g. "Next", "Next >", "→", ">", "»")
_NEXT_TEXT_RE = re.compile(
    r"^\s*(next\s*[>→»]?|next\s*page\s*[>→»]?|[>→»])\s*$",
    re.IGNORECASE,
)

# Regexes for extracting page numbers from URLs
_PAGE_QUERY_RE = re.compile(r"[?&]page=(\d+)")
_PAGE_PATH_RE = re.compile(r"/page/(\d+)")
_PAGE_PATTERN_RE = re.compile(r"(?:[?&/]page[=/])(\d+)")


def _smart_urljoin(base: str, href: str) -> str:
    """Like *urljoin* but merges query strings when *href* starts with ``?``.

    This preserves existing query parameters (e.g. ``?sort=price``) while
    adding/updating the parameters from the pagination link.
    """
    if href.startswith("?"):
        base_parts = urlparse(base)
        base_qs = parse_qs(base_parts.query)
        new_qs = parse_qs(href.lstrip("?"))
        merged_qs = {**base_qs, **new_qs}
        query = urlencode(merged_qs, doseq=True)
        return urlunparse(base_parts._replace(query=query))
    return urljoin(base, href)


def _extract_page_num(url: str) -> int:
    """Extract the page number from a URL, defaulting to 1."""
    for pattern in (_PAGE_QUERY_RE, _PAGE_PATH_RE):
        match = pattern.search(url)
        if match:
            return int(match.group(1))
    return 1


def find_next_page_url(html: str, current_url: str) -> str | None:
    """Scan HTML for a link to the next page.

    Priority:
      1. Links whose text is literally "Next", "Next >", "→", ">", "»", etc.
      2. Links whose href contains a page pattern (``page=N`` or ``/page/N``)
         with a page number greater than the current page.

    Args:
        html: Raw HTML of the current page.
        current_url: The URL of the current page (used to resolve relative
            links and determine current page number).

    Returns:
        Absolute URL of the next page, or *None* if no next page is found.
    """
    soup = BeautifulSoup(html, "html.parser")
    current_page = _extract_page_num(current_url)

    candidates: list[tuple[int, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        absolute_url = _smart_urljoin(current_url, href)

        # Skip if the link points back to the same URL
        if absolute_url == current_url:
            continue

        # Priority 1: explicit next text (case-insensitive)
        text = a.get_text(strip=True)
        if _NEXT_TEXT_RE.match(text):
            return absolute_url

        # Priority 2: URL contains a page pattern with a higher page number
        page_num = _extract_page_num(absolute_url)
        if page_num > current_page and _PAGE_PATTERN_RE.search(absolute_url):
            candidates.append((page_num, absolute_url))

    if candidates:
        # Return the lowest page number greater than current
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    return None


class Paginator:
    """Fetch all pages of a paginated listing starting from a given URL."""

    def __init__(
        self,
        *,
        fetch_html_fn=None,
        max_pages: int = 10,
    ) -> None:
        self.fetch_html = fetch_html_fn or fetch_html
        self.max_pages = max_pages

    async def fetch_all_pages(self, start_url: str) -> list[tuple[str, str]]:
        """Fetch the start URL and follow pagination links.

        Stops when no next link is found, the ``max_pages`` limit is reached,
        or a page that has already been seen is encountered.

        Args:
            start_url: The first page to fetch.

        Returns:
            A list of ``(url, html)`` tuples, one per page fetched.

        Raises:
            Exception: If the *first* page fails to fetch. Subsequent page
                failures are logged as warnings and the already-fetched pages
                are returned.
        """
        pages: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        current_url = start_url

        for _ in range(self.max_pages):
            if current_url in seen_urls:
                break

            try:
                html = await self.fetch_html(current_url)
            except Exception:
                if not pages:
                    # First page failed — propagate so the pipeline can handle
                    # it the same way it handled single-source failures before.
                    raise
                logger.warning(
                    "Pagination page failed for {} after fetching {} pages",
                    current_url,
                    len(pages),
                )
                break

            pages.append((current_url, html))
            seen_urls.add(current_url)

            next_url = find_next_page_url(html, current_url)
            if not next_url:
                break

            current_url = next_url

        return pages
