"""Pydantic data models for property listings and snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Property(BaseModel):
    """A single real estate property listing."""

    id: str  # Unique identifier (URL hash or extracted ID)
    source: str  # "firsttracts" or future source name
    source_url: str  # The URL this was scraped from
    listing_url: str  # Direct link to the listing
    title: str
    price: float
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    property_name: Optional[str] = None  # e.g. "Allegheny Springs" or "Rimfire Lodge"
    location: Optional[str] = None  # e.g. "Snowshoe Village"
    view_description: Optional[str] = None
    image_urls: list[str] = []
    description: str
    is_available: bool = True
    first_seen: datetime
    last_updated: datetime
    last_price: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_view_classification: Optional[str] = None  # "mountain", "ski_area", "other"
    ai_raw_json: Optional[str] = None  # Store the raw AI extraction response for debugging


class DailySnapshot(BaseModel):
    """Daily aggregate metrics for tracked properties."""

    date: datetime
    total_listings: int
    average_price: float
    median_price: float
    new_listings: list[str] = []
    price_changes: list[str] = []
    removed_listings: list[str] = []
