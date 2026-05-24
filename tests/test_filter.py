"""Tests for the property filtering logic."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.config import Config
from src.filter import matches_criteria
from src.models import Property


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
        "description": "A nice condo in Snowshoe Village.",
        "first_seen": datetime(2024, 1, 1),
        "last_updated": datetime(2024, 1, 1),
    }
    defaults.update(kwargs)
    return Property(**defaults)


def _make_config(**kwargs: object) -> Config:
    """Build a Config instance with sensible defaults."""
    defaults: dict[str, object] = {
        "email_recipient": "test@example.com",
        "min_price": 150_000.0,
        "max_price": 200_000.0,
        "min_bedrooms": 1,
        "max_bedrooms": 2,
        "allowed_properties": ["Allegheny Springs", "Rimfire Lodge"],
        "required_location_keywords": ["Snowshoe Village", "Snowshoe"],
    }
    defaults.update(kwargs)
    return Config(**defaults)


# ---------------------------------------------------------------------------
# Price filtering
# ---------------------------------------------------------------------------


class TestPriceFiltering:
    def test_price_within_range_passes(self) -> None:
        prop = _make_property(price=175_000.0)
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_price_at_exact_minimum_passes(self) -> None:
        prop = _make_property(price=150_000.0)
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_price_at_exact_maximum_passes(self) -> None:
        prop = _make_property(price=200_000.0)
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_price_below_minimum_fails(self) -> None:
        prop = _make_property(price=149_999.0)
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_price_above_maximum_fails(self) -> None:
        prop = _make_property(price=200_001.0)
        config = _make_config()
        assert matches_criteria(prop, config) is False


# ---------------------------------------------------------------------------
# Bedroom filtering
# ---------------------------------------------------------------------------


class TestBedroomFiltering:
    def test_bedrooms_within_range_passes(self) -> None:
        prop = _make_property(bedrooms=1)
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_bedrooms_at_exact_minimum_passes(self) -> None:
        prop = _make_property(bedrooms=1)
        config = _make_config(min_bedrooms=1)
        assert matches_criteria(prop, config) is True

    def test_bedrooms_at_exact_maximum_passes(self) -> None:
        prop = _make_property(bedrooms=2)
        config = _make_config(max_bedrooms=2)
        assert matches_criteria(prop, config) is True

    def test_bedrooms_below_minimum_fails(self) -> None:
        prop = _make_property(bedrooms=0)
        config = _make_config(min_bedrooms=1)
        assert matches_criteria(prop, config) is False

    def test_bedrooms_above_maximum_fails(self) -> None:
        prop = _make_property(bedrooms=3)
        config = _make_config(max_bedrooms=2)
        assert matches_criteria(prop, config) is False

    def test_bedrooms_none_skips_check(self) -> None:
        """If bedrooms is unknown (None), the bedroom filter should not reject."""
        prop = _make_property(bedrooms=None)
        config = _make_config()
        assert matches_criteria(prop, config) is True


# ---------------------------------------------------------------------------
# Property name filtering
# ---------------------------------------------------------------------------


class TestPropertyNameFiltering:
    def test_allowed_property_name_passes(self) -> None:
        prop = _make_property(property_name="Allegheny Springs")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_allowed_property_name_case_insensitive(self) -> None:
        prop = _make_property(property_name="allegheny springs")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_allowed_property_name_substring_match(self) -> None:
        prop = _make_property(property_name="Allegheny Springs Building A")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_disallowed_property_name_fails(self) -> None:
        prop = _make_property(property_name="Some Other Property")
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_empty_allowed_properties_list_passes_all(self) -> None:
        prop = _make_property(property_name="Any Random Property")
        config = _make_config(allowed_properties=[])
        assert matches_criteria(prop, config) is True

    def test_none_property_name_with_allowed_list_fails(self) -> None:
        prop = _make_property(property_name=None)
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_none_property_name_with_empty_allowed_list_passes(self) -> None:
        prop = _make_property(property_name=None)
        config = _make_config(allowed_properties=[])
        assert matches_criteria(prop, config) is True


# ---------------------------------------------------------------------------
# Location / keyword filtering
# ---------------------------------------------------------------------------


class TestLocationFiltering:
    def test_keyword_in_location_field_passes(self) -> None:
        prop = _make_property(location="Snowshoe Village", description="Nice place.")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_keyword_in_description_passes(self) -> None:
        prop = _make_property(location="Denver", description="Located near Snowshoe.")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_keyword_missing_fails(self) -> None:
        prop = _make_property(location="Denver", description="Nice place in Denver.")
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_empty_required_keywords_passes_all(self) -> None:
        prop = _make_property(location="Denver", description="Nice place.")
        config = _make_config(required_location_keywords=[])
        assert matches_criteria(prop, config) is True

    def test_keyword_case_insensitive(self) -> None:
        prop = _make_property(location="snowshoe village")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_keyword_in_combined_location_and_description(self) -> None:
        prop = _make_property(location="Village", description="Snowshoe resort area.")
        config = _make_config()
        assert matches_criteria(prop, config) is True


# ---------------------------------------------------------------------------
# AI view classification filtering
# ---------------------------------------------------------------------------


class TestViewClassificationFiltering:
    def test_mountain_view_passes(self) -> None:
        prop = _make_property(ai_view_classification="mountain")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_ski_area_view_passes(self) -> None:
        prop = _make_property(ai_view_classification="ski_area")
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_other_view_fails(self) -> None:
        prop = _make_property(ai_view_classification="other")
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_none_view_classification_skips_check(self) -> None:
        prop = _make_property(ai_view_classification=None)
        config = _make_config()
        assert matches_criteria(prop, config) is True


# ---------------------------------------------------------------------------
# Combined criteria
# ---------------------------------------------------------------------------


class TestCombinedCriteria:
    def test_all_criteria_match_passes(self) -> None:
        prop = _make_property(
            price=175_000.0,
            bedrooms=1,
            property_name="Allegheny Springs",
            location="Snowshoe Village",
            ai_view_classification="mountain",
        )
        config = _make_config()
        assert matches_criteria(prop, config) is True

    def test_one_criteria_fails_rejects(self) -> None:
        prop = _make_property(
            price=250_000.0,  # Too expensive
            bedrooms=1,
            property_name="Allegheny Springs",
            location="Snowshoe Village",
            ai_view_classification="mountain",
        )
        config = _make_config()
        assert matches_criteria(prop, config) is False

    def test_multiple_failures_still_rejects(self) -> None:
        prop = _make_property(
            price=250_000.0,  # Too expensive
            bedrooms=5,  # Too many bedrooms
            property_name="Unknown Property",  # Not allowed
            location="Denver",  # Missing keyword
            ai_view_classification="other",  # Bad view
        )
        config = _make_config()
        assert matches_criteria(prop, config) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_bedrooms_at_min_boundary(self) -> None:
        prop = _make_property(bedrooms=0)
        config = _make_config(min_bedrooms=0)
        assert matches_criteria(prop, config) is True

    def test_zero_price_at_min_boundary(self) -> None:
        prop = _make_property(price=0.0)
        config = _make_config(min_price=0.0)
        assert matches_criteria(prop, config) is True

    def test_very_high_price_within_range(self) -> None:
        prop = _make_property(price=1_000_000.0)
        config = _make_config(min_price=0.0, max_price=2_000_000.0)
        assert matches_criteria(prop, config) is True

    def test_no_filters_configured_passes_all(self) -> None:
        """A config with extremely permissive values should accept any property
        whose AI view classification is either missing or desirable."""
        prop = _make_property(
            price=999_999.0,
            bedrooms=99,
            property_name="Anything",
            location="Anywhere",
            ai_view_classification=None,  # None skips the view check
        )
        config = _make_config(
            min_price=0.0,
            max_price=9_999_999.0,
            min_bedrooms=0,
            max_bedrooms=999,
            allowed_properties=[],
            required_location_keywords=[],
        )
        assert matches_criteria(prop, config) is True

    def test_ai_view_other_always_rejected_even_with_no_filters(self) -> None:
        """The mountain/ski_area view rule is a hard business requirement."""
        prop = _make_property(
            price=100_000.0,
            bedrooms=1,
            property_name="Anything",
            location="Anywhere",
            ai_view_classification="other",
        )
        config = _make_config(
            min_price=0.0,
            max_price=9_999_999.0,
            min_bedrooms=0,
            max_bedrooms=999,
            allowed_properties=[],
            required_location_keywords=[],
        )
        assert matches_criteria(prop, config) is False

    def test_negative_price_rejected_when_min_is_zero(self) -> None:
        prop = _make_property(price=-1000.0)
        config = _make_config(min_price=0.0)
        assert matches_criteria(prop, config) is False
