"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pytest

from src.models import DailySnapshot, Property


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory path."""
    return tmp_path


@pytest.fixture
def sample_property_data() -> dict[str, Any]:
    """Return a valid property dictionary."""
    return {
        "id": "test-prop-001",
        "source": "firsttracts",
        "source_url": "https://www.firsttracts.com/real-estate/our-listings",
        "listing_url": "https://www.firsttracts.com/listing/123",
        "title": "Cozy Studio at Allegheny Springs",
        "price": 175_000.0,
        "bedrooms": 1,
        "bathrooms": 1.0,
        "sqft": 450,
        "property_name": "Allegheny Springs",
        "location": "Snowshoe Village",
        "view_description": "Mountain view",
        "image_urls": ["https://example.com/img1.jpg"],
        "description": "Beautiful studio condo with mountain views.",
        "is_available": True,
        "first_seen": datetime(2024, 1, 15, 10, 0, 0),
        "last_updated": datetime(2024, 1, 15, 10, 0, 0),
    }


@pytest.fixture
def sample_property(sample_property_data: dict[str, Any]) -> Property:
    """Return a validated Property model instance."""
    return Property(**sample_property_data)


@pytest.fixture
def another_property_data() -> dict[str, Any]:
    """Return a second valid property dictionary."""
    return {
        "id": "test-prop-002",
        "source": "firsttracts",
        "source_url": "https://www.firsttracts.com/real-estate/our-listings",
        "listing_url": "https://www.firsttracts.com/listing/456",
        "title": "Rimfire Lodge 1BR",
        "price": 190_000.0,
        "bedrooms": 1,
        "bathrooms": 1.5,
        "sqft": 600,
        "property_name": "Rimfire Lodge",
        "location": "Snowshoe",
        "view_description": "Ski slope view",
        "image_urls": ["https://example.com/img2.jpg", "https://example.com/img3.jpg"],
        "description": "Spacious 1BR near the slopes.",
        "is_available": True,
        "first_seen": datetime(2024, 1, 10, 8, 30, 0),
        "last_updated": datetime(2024, 1, 16, 9, 0, 0),
    }


@pytest.fixture
def sample_snapshot() -> DailySnapshot:
    """Return a validated DailySnapshot model instance."""
    return DailySnapshot(
        date=datetime(2024, 1, 15, 23, 59, 59),
        total_listings=5,
        average_price=180_000.0,
        median_price=175_000.0,
        new_listings=["test-prop-001"],
        price_changes=[],
        removed_listings=["test-prop-003"],
    )


@pytest.fixture
def populated_storage_file(temp_dir: Path) -> Path:
    """Create a pre-populated JSON storage file and return its path."""
    data = {
        "version": 1,
        "last_run": "2024-01-15T10:00:00",
        "properties": {
            "existing-001": {
                "id": "existing-001",
                "source": "firsttracts",
                "source_url": "https://example.com",
                "listing_url": "https://example.com/1",
                "title": "Existing Property",
                "price": 160_000.0,
                "bedrooms": 1,
                "description": "An existing property.",
                "is_available": True,
                "first_seen": "2024-01-01T00:00:00",
                "last_updated": "2024-01-10T00:00:00",
            }
        },
        "snapshots": [
            {
                "date": "2024-01-14T23:59:59",
                "total_listings": 1,
                "average_price": 160_000.0,
                "median_price": 160_000.0,
                "new_listings": [],
                "price_changes": [],
                "removed_listings": [],
            }
        ],
    }
    filepath = temp_dir / "properties.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return filepath


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove relevant environment variables and change to temp directory."""
    env_vars = [
        "EMAIL_RECIPIENT",
        "SOURCES",
        "ALLOWED_PROPERTIES",
        "REQUIRED_LOCATION_KEYWORDS",
        "MIN_BEDROOMS",
        "MAX_BEDROOMS",
        "MIN_PRICE",
        "MAX_PRICE",
        "AI_PROVIDER",
        "GEMINI_API_KEY",
        "KIMI_API_KEY",
        "AI_MODEL",
        "EMAIL_FROM",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_USE_TLS",
        "DRY_RUN",
        "SKIP_AI",
        "DATA_PATH",
        "RUN_FREQUENCY",
        "LOG_LEVEL",
        "MAX_PAGES_PER_SOURCE",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    # Change to temp dir so pydantic-settings doesn't find project's .env file
    monkeypatch.chdir(tmp_path)
