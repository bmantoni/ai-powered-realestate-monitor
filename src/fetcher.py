"""Async HTTP fetcher with retries and proper headers."""

from __future__ import annotations

import asyncio
import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
MAX_RETRIES = 3
BACKOFF_BASE = 1.0


async def fetch_html(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Fetch raw HTML from *url* using an async HTTP GET.

    Args:
        url: The URL to fetch.
        headers: Optional extra headers to merge with defaults.
        timeout: Request timeout. Defaults to 30 seconds total.
        max_retries: Number of retries on transient errors.

    Returns:
        The response body as a string.

    Raises:
        httpx.HTTPStatusError: On 4xx/5xx responses.
        httpx.TimeoutException: On request timeout.
        httpx.ConnectError: On connection failures.
    """
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    client_timeout = timeout or DEFAULT_TIMEOUT

    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=client_timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=request_headers)
                response.raise_for_status()
                return response.text
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_exception = exc
            # Don't retry on 4xx client errors (except 429)
            if isinstance(exc, httpx.HTTPStatusError):
                code = exc.response.status_code
                if 400 <= code < 500 and code != 429:
                    raise
            if attempt < max_retries:
                await asyncio.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

    # If we exhausted retries, re-raise the last exception
    if last_exception is not None:
        raise last_exception

    # Should never reach here, but satisfy type checker
    raise RuntimeError("Unexpected end of fetch_html")
