"""Tests for the pipeline orchestration logic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.models import DailySnapshot, Property
from src.pipeline import Pipeline
from src.storage import JsonStorage


def _make_property(**kwargs: object) -> Property:
    """Build a Property instance with sensible defaults."""
    defaults: dict[str, object] = {
        "id": "test-001",
        "source": "firsttracts",
        "source_url": "https://example.com",
        "listing_url": "https://example.com/1",
        "title": "Test Property",
        "price": 175_000.0,
        "bedrooms": 1,
        "property_name": "Allegheny Springs",
        "location": "Snowshoe Village",
        "description": "A nice condo.",
        "first_seen": datetime(2024, 1, 1, 10, 0, 0),
        "last_updated": datetime(2024, 1, 1, 10, 0, 0),
    }
    defaults.update(kwargs)
    return Property(**defaults)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        email_recipient="test@example.com",
        sources=["https://example.com/listings"],
        min_price=150_000.0,
        max_price=200_000.0,
        min_bedrooms=1,
        max_bedrooms=2,
        allowed_properties=["Allegheny Springs", "Rimfire Lodge"],
        required_location_keywords=["Snowshoe"],
        data_path=str(tmp_path / "pipeline-test.json"),
    )


@pytest.fixture
def storage(config: Config) -> JsonStorage:
    return JsonStorage(config.data_path)


@pytest.fixture
def scraper() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pipeline(config: Config, storage: JsonStorage, scraper: MagicMock) -> Pipeline:
    return Pipeline(config=config, storage=storage, scraper=scraper)


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------


class TestDiffEngine:
    @pytest.mark.asyncio
    async def test_detects_new_listing(self, pipeline: Pipeline, scraper: MagicMock, storage: JsonStorage) -> None:
        """A property not present in storage should be flagged as new."""
        fetched = [
            _make_property(id="new-001", price=175_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert "new-001" in snapshot.new_listings
        assert snapshot.price_changes == []
        assert snapshot.removed_listings == []
        assert len(properties) == 1

    @pytest.mark.asyncio
    async def test_detects_price_change(self, pipeline: Pipeline, scraper: MagicMock, storage: JsonStorage) -> None:
        """A property whose price changed since the last run should be flagged."""
        storage.upsert_property("existing-001", {
            "id": "existing-001",
            "source": "firsttracts",
            "source_url": "https://example.com",
            "listing_url": "https://example.com/1",
            "title": "Existing",
            "price": 160_000.0,
            "bedrooms": 1,
            "property_name": "Allegheny Springs",
            "location": "Snowshoe Village",
            "description": "A nice condo.",
            "is_available": True,
            "first_seen": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
        })
        storage.save()

        fetched = [
            _make_property(id="existing-001", price=170_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert "existing-001" in snapshot.price_changes
        assert snapshot.new_listings == []
        assert snapshot.removed_listings == []
        # Verify last_price was tracked in storage
        stored = storage.get_property("existing-001")
        assert stored is not None
        assert stored["last_price"] == 160_000.0
        assert stored["price"] == 170_000.0

    @pytest.mark.asyncio
    async def test_detects_removed_listing(self, pipeline: Pipeline, scraper: MagicMock, storage: JsonStorage) -> None:
        """A property in storage that is not fetched should be flagged as removed."""
        storage.upsert_property("old-001", {
            "id": "old-001",
            "source": "firsttracts",
            "source_url": "https://example.com",
            "listing_url": "https://example.com/1",
            "title": "Old Property",
            "price": 160_000.0,
            "bedrooms": 1,
            "property_name": "Allegheny Springs",
            "location": "Snowshoe Village",
            "description": "A nice condo.",
            "is_available": True,
            "first_seen": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
        })
        storage.save()

        fetched = [
            _make_property(id="active-001", price=175_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert "old-001" in snapshot.removed_listings
        assert "active-001" in snapshot.new_listings
        assert snapshot.price_changes == []
        # Verify old property is marked unavailable
        stored = storage.get_property("old-001")
        assert stored is not None
        assert stored["is_available"] is False

    @pytest.mark.asyncio
    async def test_no_changes(self, pipeline: Pipeline, scraper: MagicMock, storage: JsonStorage) -> None:
        """When the same property is fetched again with no changes, nothing is flagged."""
        storage.upsert_property("same-001", {
            "id": "same-001",
            "source": "firsttracts",
            "source_url": "https://example.com",
            "listing_url": "https://example.com/1",
            "title": "Same Property",
            "price": 175_000.0,
            "bedrooms": 1,
            "property_name": "Allegheny Springs",
            "location": "Snowshoe Village",
            "description": "A nice condo.",
            "is_available": True,
            "first_seen": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
        })
        storage.save()

        fetched = [
            _make_property(id="same-001", price=175_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert snapshot.new_listings == []
        assert snapshot.price_changes == []
        assert snapshot.removed_listings == []
        assert len(properties) == 1


# ---------------------------------------------------------------------------
# Daily snapshot calculation
# ---------------------------------------------------------------------------


class TestSnapshotCalculation:
    @pytest.mark.asyncio
    async def test_calculates_total_listings(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        fetched = [
            _make_property(id="p1", price=150_000.0),
            _make_property(id="p2", price=200_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, _ = await pipeline.run()

        assert snapshot.total_listings == 2

    @pytest.mark.asyncio
    async def test_calculates_average_price(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        fetched = [
            _make_property(id="p1", price=150_000.0),
            _make_property(id="p2", price=200_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, _ = await pipeline.run()

        assert snapshot.average_price == 175_000.0

    @pytest.mark.asyncio
    async def test_calculates_median_price_even_count(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        fetched = [
            _make_property(id="p1", price=150_000.0),
            _make_property(id="p2", price=200_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, _ = await pipeline.run()

        assert snapshot.median_price == 175_000.0

    @pytest.mark.asyncio
    async def test_calculates_median_price_odd_count(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        fetched = [
            _make_property(id="p1", price=100_000.0),
            _make_property(id="p2", price=200_000.0),
            _make_property(id="p3", price=300_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, _ = await pipeline.run()

        assert snapshot.median_price == 200_000.0

    @pytest.mark.asyncio
    async def test_calculates_median_price_single_listing(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        fetched = [
            _make_property(id="p1", price=180_000.0),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, _ = await pipeline.run()

        assert snapshot.median_price == 180_000.0

    @pytest.mark.asyncio
    async def test_empty_snapshot_when_no_listings(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        scraper.extract_listings = AsyncMock(return_value=[])

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert snapshot.total_listings == 0
        assert snapshot.average_price == 0.0
        assert snapshot.median_price == 0.0
        assert properties == []


# ---------------------------------------------------------------------------
# Filtering integration
# ---------------------------------------------------------------------------


class TestFilteringIntegration:
    @pytest.mark.asyncio
    async def test_only_relevant_properties_returned(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        """Properties that do not match criteria should be stored but not returned."""
        fetched = [
            _make_property(id="good", price=175_000.0, property_name="Allegheny Springs", location="Snowshoe Village"),
            _make_property(id="bad", price=500_000.0, property_name="Luxury Tower", location="NYC"),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert len(properties) == 1
        assert properties[0].id == "good"
        assert snapshot.total_listings == 1
        assert snapshot.average_price == 175_000.0
        # Both should be in storage, though
        assert pipeline.storage.get_property("good") is not None
        assert pipeline.storage.get_property("bad") is not None

    @pytest.mark.asyncio
    async def test_snapshot_counts_only_relevant(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        """New / price-change / removed flags should consider only relevant properties."""
        storage = pipeline.storage
        storage.upsert_property("good-old", {
            "id": "good-old",
            "source": "firsttracts",
            "source_url": "https://example.com",
            "listing_url": "https://example.com/1",
            "title": "Good Old",
            "price": 160_000.0,
            "bedrooms": 1,
            "property_name": "Allegheny Springs",
            "location": "Snowshoe Village",
            "description": "A nice condo.",
            "is_available": True,
            "first_seen": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
        })
        storage.upsert_property("bad-old", {
            "id": "bad-old",
            "source": "firsttracts",
            "source_url": "https://example.com",
            "listing_url": "https://example.com/2",
            "title": "Bad Old",
            "price": 900_000.0,
            "bedrooms": 5,
            "property_name": "Luxury Tower",
            "location": "NYC",
            "description": "Too expensive.",
            "is_available": True,
            "first_seen": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
        })
        storage.save()

        fetched = [
            _make_property(id="good-old", price=165_000.0, property_name="Allegheny Springs", location="Snowshoe Village"),
            _make_property(id="good-new", price=175_000.0, property_name="Rimfire Lodge", location="Snowshoe"),
        ]
        scraper.extract_listings = AsyncMock(return_value=fetched)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert snapshot.new_listings == ["good-new"]
        assert snapshot.price_changes == ["good-old"]
        # bad-old should be in removed_listings because it was available but not fetched
        assert "bad-old" in snapshot.removed_listings


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_one_source_fails_others_continue(self, config: Config, scraper: MagicMock, tmp_path: Path) -> None:
        """If fetching one source raises, the pipeline should continue with remaining sources."""
        config.sources = [
            "https://example.com/bad",
            "https://example.com/good",
        ]
        config.data_path = str(tmp_path / "error-test.json")
        storage = JsonStorage(config.data_path)
        pipeline = Pipeline(config=config, storage=storage, scraper=scraper)

        good_property = _make_property(id="from-good", price=175_000.0)
        scraper.extract_listings = AsyncMock(return_value=[good_property])

        with patch(
            "src.pipeline.fetch_html",
            new_callable=AsyncMock,
            side_effect=[Exception("Connection refused"), "<html>good</html>"],
        ):
            snapshot, properties = await pipeline.run()

        assert len(properties) == 1
        assert properties[0].id == "from-good"
        assert snapshot.total_listings == 1

    @pytest.mark.asyncio
    async def test_scraper_failure_continues(self, config: Config, scraper: MagicMock, tmp_path: Path) -> None:
        """If scraping one source raises, the pipeline should continue with remaining sources."""
        config.sources = [
            "https://example.com/bad",
            "https://example.com/good",
        ]
        config.data_path = str(tmp_path / "scraper-error-test.json")
        storage = JsonStorage(config.data_path)
        pipeline = Pipeline(config=config, storage=storage, scraper=scraper)

        good_property = _make_property(id="from-good", price=175_000.0)

        async def _extract(html: str, source_url: str) -> list[Property]:
            if "bad" in source_url:
                raise ValueError("Scraper error")
            return [good_property]

        scraper.extract_listings = AsyncMock(side_effect=_extract)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert len(properties) == 1
        assert properties[0].id == "from-good"

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_empty(self, pipeline: Pipeline, scraper: MagicMock) -> None:
        """If every source fails, the pipeline should return an empty snapshot gracefully."""
        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, side_effect=Exception("Boom")):
            snapshot, properties = await pipeline.run()

        assert snapshot.total_listings == 0
        assert snapshot.average_price == 0.0
        assert snapshot.median_price == 0.0
        assert properties == []


# ---------------------------------------------------------------------------
# Multi-source aggregation
# ---------------------------------------------------------------------------


class TestMultiSourceAggregation:
    @pytest.mark.asyncio
    async def test_aggregates_listings_from_multiple_sources(self, config: Config, scraper: MagicMock, tmp_path: Path) -> None:
        config.sources = [
            "https://example.com/src1",
            "https://example.com/src2",
        ]
        config.data_path = str(tmp_path / "multi-source.json")
        storage = JsonStorage(config.data_path)
        pipeline = Pipeline(config=config, storage=storage, scraper=scraper)

        async def _extract(html: str, source_url: str) -> list[Property]:
            if "src1" in source_url:
                return [_make_property(id="src1-a", price=160_000.0)]
            return [_make_property(id="src2-b", price=190_000.0)]

        scraper.extract_listings = AsyncMock(side_effect=_extract)

        with patch("src.pipeline.fetch_html", new_callable=AsyncMock, return_value="<html></html>"):
            snapshot, properties = await pipeline.run()

        assert len(properties) == 2
        ids = {p.id for p in properties}
        assert ids == {"src1-a", "src2-b"}
        assert snapshot.total_listings == 2
        assert snapshot.average_price == 175_000.0
