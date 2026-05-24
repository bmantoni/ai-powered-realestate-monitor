"""Tests for the AI scraper module.

All tests use a mock AI client to avoid external API calls.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.ai_client import MockAIClient
from src.ai_scraper import AIScraper, EXTRACTION_PROMPT, _make_absolute
from src.models import Property


class TestMakeAbsolute:
    """Test suite for URL normalization helper."""

    def test_already_absolute_url_unchanged(self):
        """Absolute URLs should be returned as-is."""
        url = "https://example.com/image.jpg"
        assert _make_absolute(url, "https://example.com/") == url

    def test_relative_url_joined_with_base(self):
        """Relative URLs should be joined with the base URL."""
        assert (
            _make_absolute("/image.jpg", "https://example.com/listings")
            == "https://example.com/image.jpg"
        )

    def test_relative_without_leading_slash(self):
        """Relative URLs without leading slash should also be resolved."""
        assert (
            _make_absolute("image.jpg", "https://example.com/listings/")
            == "https://example.com/listings/image.jpg"
        )

    def test_protocol_relative_url(self):
        """Protocol-relative URLs (//) should get the base scheme."""
        assert (
            _make_absolute("//cdn.example.com/img.jpg", "https://example.com/")
            == "https://cdn.example.com/img.jpg"
        )


class TestExtractListings:
    """Test suite for AIScraper.extract_listings."""

    @pytest.fixture
    def mock_ai_client(self):
        """Return a mock AI client with a configurable response."""
        client = MockAIClient()
        return client

    @pytest.fixture
    def scraper(self, mock_ai_client):
        """Return an AIScraper backed by the mock client."""
        return AIScraper(ai_client=mock_ai_client)

    @pytest.fixture
    def sample_ai_response(self) -> list[dict[str, Any]]:
        """Return a sample AI JSON response representing one listing."""
        return [
            {
                "id": "listing-123",
                "title": "Allegheny Springs 1BR",
                "price": 175000,
                "bedrooms": 1,
                "bathrooms": 1.0,
                "sqft": 450,
                "property_name": "Allegheny Springs",
                "location": "Snowshoe Village",
                "view_description": "Mountain view",
                "listing_url": "https://www.firsttracts.com/listing/123",
                "image_urls": ["https://www.firsttracts.com/img/123.jpg"],
                "description": "Cozy condo with great views.",
            }
        ]

    @pytest.mark.asyncio
    async def test_extract_listings_returns_property_list(
        self, scraper, mock_ai_client, sample_ai_response
    ):
        """Should return a list of Property models from AI response."""
        mock_ai_client.set_response(sample_ai_response)
        html = "<html><body>Some listings</body></html>"
        source_url = "https://www.firsttracts.com/real-estate/our-listings"

        result = await scraper.extract_listings(html, source_url)

        assert len(result) == 1
        assert isinstance(result[0], Property)
        assert result[0].id == "listing-123"
        assert result[0].title == "Allegheny Springs 1BR"
        assert result[0].price == 175000.0
        assert result[0].source == "firsttracts"
        assert result[0].source_url == source_url

    @pytest.mark.asyncio
    async def test_extract_listings_normalizes_relative_urls(
        self, scraper, mock_ai_client
    ):
        """Relative listing and image URLs should be made absolute."""
        mock_ai_client.set_response(
            [
                {
                    "id": "listing-456",
                    "title": "Rimfire Lodge",
                    "price": 190000,
                    "listing_url": "/listing/456",
                    "image_urls": ["/img/456.jpg", "thumb/456.png"],
                    "description": "Nice place",
                }
            ]
        )
        html = "<html></html>"
        source_url = "https://www.firsttracts.com/real-estate/our-listings"

        result = await scraper.extract_listings(html, source_url)

        assert result[0].listing_url == "https://www.firsttracts.com/listing/456"
        assert result[0].image_urls == [
            "https://www.firsttracts.com/img/456.jpg",
            "https://www.firsttracts.com/real-estate/thumb/456.png",
        ]

    @pytest.mark.asyncio
    async def test_extract_listings_uses_fallback_id_when_missing(
        self, scraper, mock_ai_client
    ):
        """When AI response lacks an id, one should be generated from the listing_url."""
        mock_ai_client.set_response(
            [
                {
                    "title": "Mystery Condo",
                    "price": 150000,
                    "listing_url": "https://example.com/listing/abc",
                    "description": "No id here",
                }
            ]
        )

        result = await scraper.extract_listings("<html></html>", "https://example.com/")

        assert result[0].id is not None
        assert result[0].id != ""
        # Should be deterministic based on URL (includes path for uniqueness)
        expected_id = "example_com_listing_abc"
        assert result[0].id == expected_id

    @pytest.mark.asyncio
    async def test_extract_listings_truncates_html_to_150k(self, scraper, mock_ai_client):
        """HTML longer than 150k characters should be truncated in the prompt."""
        mock_ai_client.set_response([])
        huge_html = "A" * 200_000
        source_url = "https://example.com/"

        await scraper.extract_listings(huge_html, source_url)

        prompt = mock_ai_client.last_prompt
        # The prompt should contain truncated HTML
        assert len(prompt) < 200_000
        # The placeholder HTML in prompt should be at most 150k chars
        html_in_prompt = prompt.replace(EXTRACTION_PROMPT.format(html=""), "")
        # Actually, check that the html portion is truncated
        assert "A" * 150_001 not in prompt
        assert "A" * 149_999 in prompt  # truncated but still large

    @pytest.mark.asyncio
    async def test_extract_listings_caches_results(self, scraper, mock_ai_client):
        """Calling extract_listings twice with same html should use cache."""
        mock_ai_client.set_response(
            [
                {
                    "id": "cached",
                    "title": "Cached Property",
                    "price": 100000,
                    "listing_url": "https://example.com/1",
                    "description": "Cache me",
                }
            ]
        )
        html = "<html>same</html>"
        source_url = "https://example.com/"

        result1 = await scraper.extract_listings(html, source_url)
        result2 = await scraper.extract_listings(html, source_url)

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].id == result2[0].id
        # AI client should only have been called once
        assert mock_ai_client.call_count == 1

    @pytest.mark.asyncio
    async def test_extract_listings_cache_busted_on_different_html(
        self, scraper, mock_ai_client
    ):
        """Different HTML should trigger a new AI call."""
        mock_ai_client.set_response([])

        await scraper.extract_listings("<html>v1</html>", "https://example.com/")
        await scraper.extract_listings("<html>v2</html>", "https://example.com/")

        assert mock_ai_client.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_listings_sets_first_seen_and_last_updated(
        self, scraper, mock_ai_client, sample_ai_response
    ):
        """Properties should have first_seen and last_updated set to now."""
        mock_ai_client.set_response(sample_ai_response)

        before = datetime.utcnow()
        result = await scraper.extract_listings("<html></html>", "https://example.com/")
        after = datetime.utcnow()

        prop = result[0]
        assert before <= prop.first_seen <= after
        assert before <= prop.last_updated <= after

    @pytest.mark.asyncio
    async def test_extract_listings_stores_raw_ai_json(self, scraper, mock_ai_client):
        """Each property should store the raw AI response JSON."""
        mock_ai_client.set_response(
            [
                {
                    "id": "raw-test",
                    "title": "Raw",
                    "price": 123000,
                    "listing_url": "https://example.com/1",
                    "description": "Test",
                    "extra_field": "preserved",
                }
            ]
        )

        result = await scraper.extract_listings("<html></html>", "https://example.com/")

        raw = json.loads(result[0].ai_raw_json)
        assert raw["extra_field"] == "preserved"
        assert raw["id"] == "raw-test"

    @pytest.mark.asyncio
    async def test_extract_listings_preserves_optional_fields(self, scraper, mock_ai_client):
        """Optional fields like bathrooms, sqft should be preserved when present."""
        mock_ai_client.set_response(
            [
                {
                    "id": "opt",
                    "title": "Optional",
                    "price": 200000,
                    "listing_url": "https://example.com/1",
                    "description": "Desc",
                    "bedrooms": 2,
                    "bathrooms": 2.5,
                    "sqft": 900,
                    "property_name": "Rimfire Lodge",
                    "location": "Snowshoe Village",
                    "view_description": "Ski area view",
                }
            ]
        )

        result = await scraper.extract_listings("<html></html>", "https://example.com/")
        prop = result[0]

        assert prop.bedrooms == 2
        assert prop.bathrooms == 2.5
        assert prop.sqft == 900
        assert prop.property_name == "Rimfire Lodge"
        assert prop.location == "Snowshoe Village"
        assert prop.view_description == "Ski area view"

    @pytest.mark.asyncio
    async def test_extract_listings_handles_ai_error(self, scraper, mock_ai_client):
        """AI client errors should propagate as exceptions."""
        mock_ai_client.set_side_effect(RuntimeError("AI service down"))

        with pytest.raises(RuntimeError, match="AI service down"):
            await scraper.extract_listings("<html></html>", "https://example.com/")

    @pytest.mark.asyncio
    async def test_extract_listings_skips_invalid_items(self, scraper, mock_ai_client):
        """Items missing required fields like title or price should be skipped."""
        mock_ai_client.set_response(
            [
                {
                    "id": "valid",
                    "title": "Valid",
                    "price": 150000,
                    "listing_url": "https://example.com/valid",
                    "description": "OK",
                },
                {
                    "id": "invalid",
                    # missing title and price
                    "listing_url": "https://example.com/invalid",
                },
            ]
        )

        result = await scraper.extract_listings("<html></html>", "https://example.com/")

        assert len(result) == 1
        assert result[0].id == "valid"
