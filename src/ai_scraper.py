"""AI-powered HTML scraper that extracts structured Property data."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.models import Property

if TYPE_CHECKING:
    from src.ai_client import AIClient

HTML_TRUNCATION_LIMIT = 150_000

EXTRACTION_PROMPT = """
You are a real estate listing extractor. Given the HTML content of a real estate listings page, extract ALL property listings into a structured JSON array.

For each listing, extract:
- title: The listing title/property name
- price: Price as a number (no commas, no $ sign)
- bedrooms: Number of bedrooms (integer)
- bathrooms: Number of bathrooms (float, optional)
- sqft: Square footage (integer, optional)
- property_name: Building/property complex name (e.g., "Allegheny Springs", "Rimfire Lodge")
- location: Location description (e.g., "Snowshoe Village")
- view_description: Any description of the view
- listing_url: Direct URL to the listing detail page (make absolute if relative)
- image_urls: Array of image URLs (make absolute if relative)
- description: Full property description text
- id: A unique identifier for this listing (extract from URL or data attributes if available)

Return ONLY a valid JSON array. No markdown, no explanation.
Example: [{{"title": "...", "price": 175000, ...}}]

HTML Content:
{html}
"""


def _make_absolute(url: str, base_url: str) -> str:
    """Resolve a possibly-relative *url* against *base_url*."""
    if not url:
        return url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme:
        # Already absolute
        return url
    return urllib.parse.urljoin(base_url, url)


def _extract_source_name(source_url: str) -> str:
    """Derive a short source identifier from a URL hostname."""
    parsed = urllib.parse.urlparse(source_url)
    netloc = parsed.netloc or "unknown"
    # Remove www. prefix and TLD
    name = re.sub(r"^www\.", "", netloc)
    name = name.split(".")[0]
    return name


def _generate_id_from_url(listing_url: str) -> str:
    """Create a deterministic, filesystem-safe id from a listing URL."""
    parsed = urllib.parse.urlparse(listing_url)
    path = parsed.path.strip("/")
    # Replace non-alphanumeric with underscore
    safe = re.sub(r"[^a-zA-Z0-9]", "_", f"{parsed.netloc}_{path}")
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_")


def _cache_key(source_url: str, html: str) -> str:
    """Return a deterministic cache key for a (URL, HTML) pair."""
    html_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    return f"{source_url}:{html_hash}"


class AIScraper:
    """Scrape structured property listings from raw HTML using an AI client."""

    def __init__(self, ai_client: AIClient) -> None:
        self._ai = ai_client
        self._cache: dict[str, list[Property]] = {}

    async def extract_listings(self, html: str, source_url: str) -> list[Property]:
        """Extract Property listings from *html* originating from *source_url*.

        Results are cached by (source_url + html hash) to avoid re-scraping
        unchanged pages.

        Args:
            html: Raw HTML content of the listings page.
            source_url: The URL the HTML was fetched from.

        Returns:
            A list of validated Property models.

        Raises:
            Exception: Propagated from the AI client on failure.
        """
        cache_key = _cache_key(source_url, html)
        if cache_key in self._cache:
            return self._cache[cache_key]

        truncated = html[:HTML_TRUNCATION_LIMIT]
        prompt = EXTRACTION_PROMPT.format(html=truncated)
        response = await self._ai.generate_json(prompt)

        listings: list[Property] = []
        now = datetime.now(timezone.utc)
        source_name = _extract_source_name(source_url)

        for item in response:
            if not isinstance(item, dict):
                continue

            title = item.get("title")
            price = item.get("price")
            listing_url = item.get("listing_url")

            # Skip items missing required fields
            if not title or price is None or not listing_url:
                continue

            listing_id = item.get("id") or _generate_id_from_url(str(listing_url))

            image_urls = [
                _make_absolute(str(u), source_url)
                for u in item.get("image_urls", [])
                if u
            ]

            prop = Property(
                id=str(listing_id),
                source=source_name,
                source_url=source_url,
                listing_url=_make_absolute(str(listing_url), source_url),
                title=str(title),
                price=float(price),
                bedrooms=item.get("bedrooms"),
                bathrooms=item.get("bathrooms"),
                sqft=item.get("sqft"),
                property_name=item.get("property_name"),
                location=item.get("location"),
                view_description=item.get("view_description"),
                image_urls=image_urls,
                description=item.get("description") or "",
                is_available=True,
                first_seen=now,
                last_updated=now,
                ai_raw_json=json.dumps(item),
            )
            listings.append(prop)

        self._cache[cache_key] = listings
        return listings
