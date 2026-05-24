"""Tests for the HTTP fetcher module.

All tests use mocked HTTP responses to avoid external network calls.
"""

from __future__ import annotations

import pytest
import httpx
import respx
from httpx import Response

from src.fetcher import fetch_html


@pytest.mark.asyncio
class TestFetchHtml:
    """Test suite for fetch_html async function."""

    @respx.mock
    async def test_fetch_html_returns_content(self):
        """Successful fetch should return the response text."""
        route = respx.get("https://example.com/listings").mock(
            return_value=Response(200, text="<html><body>Hello</body></html>")
        )

        result = await fetch_html("https://example.com/listings")

        assert result == "<html><body>Hello</body></html>"
        assert route.called is True

    @respx.mock
    async def test_fetch_html_sends_user_agent_header(self):
        """Fetch should include a proper User-Agent header."""
        route = respx.get("https://example.com/listings").mock(
            return_value=Response(200, text="OK")
        )

        await fetch_html("https://example.com/listings")

        request = route.calls.last.request
        assert "user-agent" in request.headers
        assert "Mozilla" in request.headers["user-agent"]

    @respx.mock
    async def test_fetch_html_raises_on_404(self):
        """HTTP 404 should raise an HTTPStatusError."""
        respx.get("https://example.com/missing").mock(
            return_value=Response(404, text="Not Found")
        )

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_html("https://example.com/missing")

    @respx.mock
    async def test_fetch_html_raises_on_500(self):
        """HTTP 500 should raise an HTTPStatusError."""
        respx.get("https://example.com/error").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_html("https://example.com/error")

    @respx.mock
    async def test_fetch_html_raises_on_timeout(self):
        """Request timeout should raise a TimeoutException."""
        respx.get("https://example.com/slow").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        with pytest.raises(httpx.TimeoutException):
            await fetch_html("https://example.com/slow")

    @respx.mock
    async def test_fetch_html_raises_on_connection_error(self):
        """Connection error should raise a ConnectError."""
        respx.get("https://example.com/down").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.ConnectError):
            await fetch_html("https://example.com/down")

    @respx.mock
    async def test_fetch_html_follows_redirects(self):
        """Fetcher should follow HTTP redirects automatically."""
        route = respx.get("https://example.com/redirected").mock(
            return_value=Response(200, text="Final content")
        )
        respx.get("https://example.com/redirect").mock(
            return_value=Response(301, headers={"Location": "https://example.com/redirected"})
        )

        result = await fetch_html("https://example.com/redirect")

        assert result == "Final content"
        assert route.called is True
