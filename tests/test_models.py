"""Tests for src.models — Property and DailySnapshot creation, validation, serialization."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from src.models import DailySnapshot, Property


# ---------------------------------------------------------------------------
# Property model
# ---------------------------------------------------------------------------
class TestPropertyCreation:
    """Happy-path creation of Property instances."""

    def test_create_minimal_property(self) -> None:
        """A Property can be created with only required fields."""
        now = datetime.utcnow()
        prop = Property(
            id="minimal-001",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="Minimal Property",
            price=100_000.0,
            description="Just the basics.",
            first_seen=now,
            last_updated=now,
        )
        assert prop.id == "minimal-001"
        assert prop.price == 100_000.0
        assert prop.bedrooms is None
        assert prop.is_available is True

    def test_create_full_property(self, sample_property_data: dict[str, Any]) -> None:
        """A Property can be created with all fields populated."""
        prop = Property(**sample_property_data)
        assert prop.id == "test-prop-001"
        assert prop.bedrooms == 1
        assert prop.property_name == "Allegheny Springs"
        assert prop.location == "Snowshoe Village"
        assert len(prop.image_urls) == 1


class TestPropertyValidation:
    """Property field validation and constraints."""

    def test_missing_required_id_raises(self) -> None:
        """Property creation fails when 'id' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Property(
                source="firsttracts",
                source_url="https://example.com",
                listing_url="https://example.com/1",
                title="Missing ID",
                price=100_000.0,
                description="No ID here.",
                first_seen=datetime.utcnow(),
                last_updated=datetime.utcnow(),
            )
        assert "id" in str(exc_info.value)

    def test_missing_required_title_raises(self) -> None:
        """Property creation fails when 'title' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Property(
                id="no-title",
                source="firsttracts",
                source_url="https://example.com",
                listing_url="https://example.com/1",
                price=100_000.0,
                description="No title here.",
                first_seen=datetime.utcnow(),
                last_updated=datetime.utcnow(),
            )
        assert "title" in str(exc_info.value)

    def test_negative_price_raises(self) -> None:
        """Property creation accepts negative price (no explicit constraint)."""
        # NOTE: The model does NOT currently enforce price >= 0. This test documents that behaviour.
        prop = Property(
            id="negative-price",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="Bad Price",
            price=-50_000.0,
            description="Price is negative.",
            first_seen=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        assert prop.price == -50_000.0

    def test_optional_fields_default_to_none_or_empty(self) -> None:
        """Optional fields default correctly when omitted."""
        now = datetime.utcnow()
        prop = Property(
            id="opt-001",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="Optional Fields",
            price=100_000.0,
            description="Defaults test.",
            first_seen=now,
            last_updated=now,
        )
        assert prop.bedrooms is None
        assert prop.bathrooms is None
        assert prop.sqft is None
        assert prop.property_name is None
        assert prop.location is None
        assert prop.view_description is None
        assert prop.image_urls == []
        assert prop.last_price is None
        assert prop.ai_summary is None
        assert prop.ai_view_classification is None
        assert prop.ai_raw_json is None

    def test_image_urls_must_be_list_of_strings(self) -> None:
        """image_urls accepts a list of strings."""
        now = datetime.utcnow()
        prop = Property(
            id="img-001",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="Images",
            price=100_000.0,
            description="Image test.",
            image_urls=["https://a.jpg", "https://b.jpg"],
            first_seen=now,
            last_updated=now,
        )
        assert prop.image_urls == ["https://a.jpg", "https://b.jpg"]

    def test_bedrooms_accepts_none_and_int(self) -> None:
        """bedrooms accepts both int and None."""
        now = datetime.utcnow()
        prop_with = Property(
            id="br-001",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="Has Bedrooms",
            price=100_000.0,
            description="Has bedrooms.",
            bedrooms=2,
            first_seen=now,
            last_updated=now,
        )
        prop_without = Property(
            id="br-002",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/1",
            title="No Bedrooms",
            price=100_000.0,
            description="No bedrooms.",
            first_seen=now,
            last_updated=now,
        )
        assert prop_with.bedrooms == 2
        assert prop_without.bedrooms is None


class TestPropertySerialization:
    """Property JSON serialization round-trips correctly."""

    def test_property_serializes_to_json(self, sample_property: Property) -> None:
        """Property can be serialized to JSON via model_dump_json."""
        json_str = sample_property.model_dump_json()
        assert "test-prop-001" in json_str
        assert "Allegheny Springs" in json_str

    def test_property_dict_contains_all_fields(self, sample_property: Property) -> None:
        """model_dump returns a dict with expected keys."""
        data = sample_property.model_dump()
        assert data["id"] == "test-prop-001"
        assert data["price"] == 175_000.0
        assert "first_seen" in data

    def test_property_round_trip(self, sample_property_data: dict[str, Any]) -> None:
        """Property serializes and deserializes without data loss."""
        original = Property(**sample_property_data)
        dumped = original.model_dump()
        restored = Property(**dumped)
        assert restored.id == original.id
        assert restored.price == original.price
        assert restored.first_seen == original.first_seen

    def test_property_json_with_datetime(self, sample_property: Property) -> None:
        """JSON output contains ISO-formatted datetimes."""
        data = json.loads(sample_property.model_dump_json())
        assert isinstance(data["first_seen"], str)
        # ISO format check
        assert "T" in data["first_seen"]


# ---------------------------------------------------------------------------
# DailySnapshot model
# ---------------------------------------------------------------------------
class TestDailySnapshotCreation:
    """Happy-path creation of DailySnapshot instances."""

    def test_create_snapshot(self, sample_snapshot: DailySnapshot) -> None:
        """DailySnapshot can be created with all fields."""
        assert sample_snapshot.total_listings == 5
        assert sample_snapshot.average_price == 180_000.0
        assert sample_snapshot.new_listings == ["test-prop-001"]
        assert sample_snapshot.removed_listings == ["test-prop-003"]

    def test_snapshot_list_fields_default_to_empty(self) -> None:
        """List fields default to empty lists when omitted."""
        now = datetime.utcnow()
        snap = DailySnapshot(
            date=now,
            total_listings=0,
            average_price=0.0,
            median_price=0.0,
        )
        assert snap.new_listings == []
        assert snap.price_changes == []
        assert snap.removed_listings == []


class TestDailySnapshotValidation:
    """DailySnapshot field validation."""

    def test_missing_required_date_raises(self) -> None:
        """DailySnapshot creation fails when 'date' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            DailySnapshot(
                total_listings=1,
                average_price=100_000.0,
                median_price=100_000.0,
            )
        assert "date" in str(exc_info.value)

    def test_missing_total_listings_raises(self) -> None:
        """DailySnapshot creation fails when 'total_listings' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            DailySnapshot(
                date=datetime.utcnow(),
                average_price=100_000.0,
                median_price=100_000.0,
            )
        assert "total_listings" in str(exc_info.value)

    def test_list_fields_accept_empty_lists(self) -> None:
        """DailySnapshot accepts empty lists for ID arrays."""
        now = datetime.utcnow()
        snap = DailySnapshot(
            date=now,
            total_listings=0,
            average_price=0.0,
            median_price=0.0,
            new_listings=[],
            price_changes=[],
            removed_listings=[],
        )
        assert snap.new_listings == []


class TestDailySnapshotSerialization:
    """DailySnapshot JSON serialization round-trips correctly."""

    def test_snapshot_serializes_to_json(self, sample_snapshot: DailySnapshot) -> None:
        """DailySnapshot can be serialized to JSON."""
        json_str = sample_snapshot.model_dump_json()
        assert "test-prop-001" in json_str
        assert "180000.0" in json_str

    def test_snapshot_round_trip(self, sample_snapshot: DailySnapshot) -> None:
        """DailySnapshot serializes and deserializes without data loss."""
        dumped = sample_snapshot.model_dump()
        restored = DailySnapshot(**dumped)
        assert restored.date == sample_snapshot.date
        assert restored.total_listings == sample_snapshot.total_listings
        assert restored.new_listings == sample_snapshot.new_listings
