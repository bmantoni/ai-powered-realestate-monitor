"""Tests for pagination logic.

All tests use mocked fetch functions to avoid external network calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.paginator import Paginator, find_next_page_url


# ---------------------------------------------------------------------------
# find_next_page_url
# ---------------------------------------------------------------------------


class TestFindNextPageUrl:
    """Test suite for the pagination link detection helper."""

    def test_no_pagination_returns_none(self) -> None:
        """When there are no pagination links, return None."""
        html = "<html><body><div class='listings'>...</div></body></html>"
        assert find_next_page_url(html, "https://example.com/listings") is None

    def test_finds_next_link_by_text(self) -> None:
        """Detect 'Next' text in anchor tags."""
        html = '<html><body><a href="?page=2">Next</a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/listings?page=2"

    def test_finds_next_link_by_arrow_text(self) -> None:
        """Detect arrow characters like → in anchor text."""
        html = '<html><body><a href="/listings/page/2">→</a></body></html>'
        result = find_next_page_url(html, "https://example.com")
        assert result == "https://example.com/listings/page/2"

    def test_finds_next_link_by_chevron_text(self) -> None:
        """Detect '>' or '>>' in anchor text."""
        html = '<html><body><a href="/listings?page=2">Next &gt;</a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/listings?page=2"

    def test_finds_next_link_by_url_pattern(self) -> None:
        """When no explicit 'Next' text, look for page=N pattern with higher number."""
        html = (
            '<html><body>'
            '<a href="https://example.com/listings">1</a> '
            '<a href="https://example.com/listings?page=2">2</a> '
            '<a href="https://example.com/listings?page=3">3</a>'
            '</body></html>'
        )
        result = find_next_page_url(html, "https://example.com/listings?page=1")
        assert result == "https://example.com/listings?page=2"

    def test_prefers_next_text_over_number(self) -> None:
        """Explicit 'Next' text should be preferred over plain page numbers."""
        html = (
            '<html><body>'
            '<a href="?page=3">3</a>'
            '<a href="?page=2">Next</a>'
            '</body></html>'
        )
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/listings?page=2"

    def test_handles_relative_urls(self) -> None:
        """Relative paths should be resolved to absolute URLs."""
        html = '<html><body><a href="/page/2">Next ></a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/page/2"

    def test_handles_query_relative_urls(self) -> None:
        """Query-only hrefs like ?page=2 should be resolved."""
        html = '<html><body><a href="?page=2">Next</a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings?sort=price")
        assert result == "https://example.com/listings?sort=price&page=2"

    def test_handles_protocol_relative_urls(self) -> None:
        """Protocol-relative URLs like //example.com/page/2 should be resolved."""
        html = '<html><body><a href="//example.com/page/2">Next</a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/page/2"

    def test_skips_empty_and_anchor_hrefs(self) -> None:
        """Empty hrefs, #fragments, and javascript: should be ignored."""
        html = (
            '<html><body>'
            '<a href="#">Top</a>'
            '<a href="javascript:void(0)">Click</a>'
            '<a href="">Empty</a>'
            '<a href="?page=2">Next</a>'
            '</body></html>'
        )
        result = find_next_page_url(html, "https://example.com/listings")
        assert result == "https://example.com/listings?page=2"

    def test_skips_same_url(self) -> None:
        """Don't return the same URL as the current page."""
        html = '<html><body><a href="https://example.com/listings">Next</a></body></html>'
        result = find_next_page_url(html, "https://example.com/listings")
        assert result is None

    def test_ignores_lower_page_numbers(self) -> None:
        """Don't go backwards in pagination."""
        html = (
            '<html><body>'
            '<a href="?page=1">Prev</a>'
            '<a href="?page=3">3</a>'
            '</body></html>'
        )
        result = find_next_page_url(html, "https://example.com/listings?page=2")
        assert result == "https://example.com/listings?page=3"

    def test_no_next_on_last_page(self) -> None:
        """When current page is the highest numbered page, return None."""
        html = (
            '<html><body>'
            '<a href="?page=1">1</a>'
            '<a href="?page=2">2</a>'
            '</body></html>'
        )
        result = find_next_page_url(html, "https://example.com/listings?page=2")
        assert result is None


# ---------------------------------------------------------------------------
# Paginator
# ---------------------------------------------------------------------------


class TestPaginator:
    """Test suite for the Paginator class."""

    @pytest.mark.asyncio
    async def test_single_page_no_pagination(self) -> None:
        """If the first page has no next link, return just that page."""
        fetch_mock = AsyncMock(return_value="<html><body>page 1</body></html>")
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 1
        assert pages[0] == ("https://example.com/listings", "<html><body>page 1</body></html>")
        fetch_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_pages_follows_next_links(self) -> None:
        """Follow next links across multiple pages and collect all HTML."""

        async def _fetch(url: str) -> str:
            if url == "https://example.com/listings":
                return '<html><body><a href="?page=2">Next</a>page 1</body></html>'
            if "page=2" in url:
                return '<html><body><a href="?page=3">Next</a>page 2</body></html>'
            if "page=3" in url:
                return "<html><body>page 3</body></html>"
            return ""

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 3
        assert pages[0][0] == "https://example.com/listings"
        assert pages[1][0] == "https://example.com/listings?page=2"
        assert pages[2][0] == "https://example.com/listings?page=3"
        assert pages[1][1] == '<html><body><a href="?page=3">Next</a>page 2</body></html>'
        assert fetch_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_stops_when_no_next_link(self) -> None:
        """Stop fetching when a page has no next pagination link."""

        async def _fetch(url: str) -> str:
            if "page=2" in url:
                return "<html><body>last page</body></html>"
            return '<html><body><a href="?page=2">Next</a>page 1</body></html>'

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 2
        assert fetch_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_respects_max_pages_limit(self) -> None:
        """Do not exceed the configured max_pages limit."""

        async def _fetch(url: str) -> str:
            page_num = 1
            if "page=" in url:
                page_num = int(url.split("page=")[-1])
            next_page = page_num + 1
            return (
                f'<html><body><a href="?page={next_page}">Next</a>page {page_num}</body></html>'
            )

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=3)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 3
        assert fetch_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_handles_errors_on_subsequent_pages_gracefully(self) -> None:
        """If a subsequent page fails, log a warning and return pages fetched so far."""

        async def _fetch(url: str) -> str:
            if "page=2" in url:
                raise RuntimeError("Server error")
            return '<html><body><a href="?page=2">Next</a>page 1</body></html>'

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 1
        assert pages[0][0] == "https://example.com/listings"
        assert fetch_mock.await_count == 2  # page 1 succeeded, page 2 failed

    @pytest.mark.asyncio
    async def test_first_page_failure_raises(self) -> None:
        """If the very first page fails, propagate the exception."""
        fetch_mock = AsyncMock(side_effect=RuntimeError("Connection refused"))
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        with pytest.raises(RuntimeError, match="Connection refused"):
            await paginator.fetch_all_pages("https://example.com/listings")

    @pytest.mark.asyncio
    async def test_correctly_constructs_absolute_urls(self) -> None:
        """Relative pagination links are converted to absolute URLs before fetching."""

        async def _fetch(url: str) -> str:
            if "page/2" in url:
                return "<html><body>page 2</body></html>"
            return '<html><body><a href="/listings/page/2">Next</a>page 1</body></html>'

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com")

        assert len(pages) == 2
        assert pages[1][0] == "https://example.com/listings/page/2"

    @pytest.mark.asyncio
    async def test_avoids_fetching_same_url_twice(self) -> None:
        """If next link points back to current URL, stop to avoid infinite loop."""

        async def _fetch(url: str) -> str:
            return '<html><body><a href="https://example.com/listings">Next</a>page</body></html>'

        fetch_mock = AsyncMock(side_effect=_fetch)
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        pages = await paginator.fetch_all_pages("https://example.com/listings")

        assert len(pages) == 1
        assert fetch_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_continues_to_next_source_when_paginator_fails(self) -> None:
        """This is more of a pipeline concern, but the paginator itself should not swallow first-page errors."""
        fetch_mock = AsyncMock(side_effect=RuntimeError("Boom"))
        paginator = Paginator(fetch_html_fn=fetch_mock, max_pages=10)

        with pytest.raises(RuntimeError, match="Boom"):
            await paginator.fetch_all_pages("https://example.com/listings")
