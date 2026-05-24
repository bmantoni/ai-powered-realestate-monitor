"""Pydantic settings with environment variable support."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_parse_enum_str=True,
        extra="ignore",
    )

    # Sources: list of URLs to scrape
    sources: List[str] = Field(
        default_factory=lambda: ["https://www.firsttracts.com/real-estate/our-listings"],
        description="List of URLs to scrape for property listings.",
    )

    # Pagination
    max_pages_per_source: int = Field(
        default=10,
        ge=1,
        description="Maximum number of pages to fetch per source.",
    )

    # Filtering criteria
    allowed_properties: List[str] = Field(
        default_factory=lambda: ["Allegheny Springs", "Rimfire Lodge"],
        description="Allowed property complex names.",
    )
    required_location_keywords: List[str] = Field(
        default_factory=lambda: ["Snowshoe Village", "Snowshoe"],
        description="Keywords that must appear in location or description.",
    )
    min_bedrooms: int = Field(default=1, ge=0)
    max_bedrooms: int = Field(default=1, ge=0)
    min_price: float = Field(default=150_000, ge=0)
    max_price: float = Field(default=200_000, ge=0)

    # AI
    ai_provider: str = Field(default="gemini", description="AI provider: gemini or kimi")
    gemini_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    ai_model: Optional[str] = Field(default=None, description="Override default model.")

    # Email
    email_recipient: str = Field(..., description="Primary recipient email address.")
    email_from: str = Field(default="your-email@gmail.com")
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server hostname.")
    smtp_port: int = Field(default=587, description="SMTP server port.")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username (usually your email address).")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password or app-specific password.")
    smtp_use_tls: bool = Field(default=True, description="Use TLS encryption for SMTP.")

    # Execution mode
    dry_run: bool = Field(
        default=False,
        description="If True, fetch and process but don't send email.",
    )
    skip_ai: bool = Field(
        default=False,
        description="If True, skip AI enrichment (faster local testing).",
    )

    # Persistence
    data_path: str = Field(default="./data/properties.json")

    # Scheduling
    run_frequency: str = Field(
        default="0 8 * * *",
        description="Cron expression for run frequency.",
    )

    # Logging
    log_level: str = Field(default="INFO")
