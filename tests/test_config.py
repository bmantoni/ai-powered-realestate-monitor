"""Tests for src.config.Config — environment loading, defaults, and validation."""

from __future__ import annotations

import os
from typing import Any

import pytest

from src.config import Config


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
class TestConfigDefaults:
    """Ensure default values are applied when no env vars are present."""

    def test_default_sources(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default sources list is populated."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.sources == ["https://www.firsttracts.com/real-estate/our-listings"]

    def test_default_allowed_properties(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default allowed properties list is populated."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.allowed_properties == ["Allegheny Springs", "Rimfire Lodge"]

    def test_default_location_keywords(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default location keywords are populated."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.required_location_keywords == ["Snowshoe Village", "Snowshoe"]

    def test_default_bedroom_range(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default min and max bedrooms are 1."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.min_bedrooms == 1
        assert config.max_bedrooms == 1

    def test_default_price_range(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default price range is 150k–200k."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.min_price == 150_000
        assert config.max_price == 200_000

    def test_default_ai_provider(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default AI provider is gemini."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.ai_provider == "gemini"

    def test_default_email_from(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default sender email is snowshoe-bot@example.com."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.email_from == "snowshoe-bot@example.com"

    def test_default_smtp_provider(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default SMTP provider is sendgrid."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.smtp_provider == "sendgrid"

    def test_default_flags(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """dry_run and skip_ai default to False."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.dry_run is False
        assert config.skip_ai is False

    def test_default_data_path(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default data path is ./data/properties.json."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.data_path == "./data/properties.json"

    def test_default_run_frequency(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default cron expression is 0 8 * * *."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.run_frequency == "0 8 * * *"

    def test_default_log_level(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default log level is INFO."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        config = Config()
        assert config.log_level == "INFO"


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------
class TestConfigValidation:
    """Ensure required fields and constraints are enforced."""

    def test_email_recipient_is_required(self, clean_env: None) -> None:
        """Config raises ValidationError when EMAIL_RECIPIENT is missing."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            Config()

    def test_min_bedrooms_must_be_non_negative(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """min_bedrooms rejects negative values."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("MIN_BEDROOMS", "-1")
        with pytest.raises(Exception):  # pydantic.ValidationError
            Config()

    def test_max_bedrooms_must_be_non_negative(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """max_bedrooms rejects negative values."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("MAX_BEDROOMS", "-1")
        with pytest.raises(Exception):  # pydantic.ValidationError
            Config()

    def test_min_price_must_be_non_negative(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """min_price rejects negative values."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("MIN_PRICE", "-1000")
        with pytest.raises(Exception):  # pydantic.ValidationError
            Config()

    def test_max_price_must_be_non_negative(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """max_price rejects negative values."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("MAX_PRICE", "-1000")
        with pytest.raises(Exception):  # pydantic.ValidationError
            Config()


# ---------------------------------------------------------------------------
# Environment-variable overrides
# ---------------------------------------------------------------------------
class TestConfigEnvOverrides:
    """Ensure env vars are correctly parsed and override defaults."""

    def test_sources_override(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """SOURCES env var overrides default sources list (JSON-encoded list)."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("SOURCES", '["https://a.com", "https://b.com"]')
        config = Config()
        assert config.sources == ["https://a.com", "https://b.com"]

    def test_allowed_properties_override(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """ALLOWED_PROPERTIES env var overrides default list (JSON-encoded list)."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("ALLOWED_PROPERTIES", '["Mountain Lodge"]')
        config = Config()
        assert config.allowed_properties == ["Mountain Lodge"]

    def test_booleans_from_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """DRY_RUN and SKIP_AI are parsed as booleans."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("DRY_RUN", "true")
        monkeypatch.setenv("SKIP_AI", "1")
        config = Config()
        assert config.dry_run is True
        assert config.skip_ai is True

    def test_numeric_fields_from_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """MIN_BEDROOMS, MAX_BEDROOMS, MIN_PRICE, MAX_PRICE are parsed as numbers."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("MIN_BEDROOMS", "2")
        monkeypatch.setenv("MAX_BEDROOMS", "3")
        monkeypatch.setenv("MIN_PRICE", "100000")
        monkeypatch.setenv("MAX_PRICE", "300000")
        config = Config()
        assert config.min_bedrooms == 2
        assert config.max_bedrooms == 3
        assert config.min_price == 100_000
        assert config.max_price == 300_000

    def test_api_keys_from_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key env vars are loaded as strings."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-123")
        monkeypatch.setenv("KIMI_API_KEY", "kimi-key-456")
        monkeypatch.setenv("SENDGRID_API_KEY", "sendgrid-key-789")
        config = Config()
        assert config.gemini_api_key == "gemini-key-123"
        assert config.kimi_api_key == "kimi-key-456"
        assert config.sendgrid_api_key == "sendgrid-key-789"

    def test_extra_env_vars_ignored(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Extra environment variables do not cause validation errors."""
        monkeypatch.setenv("EMAIL_RECIPIENT", "test@example.com")
        monkeypatch.setenv("UNKNOWN_VAR", "should_be_ignored")
        config = Config()
        assert hasattr(config, "email_recipient")


# ---------------------------------------------------------------------------
# .env file loading (mocked)
# ---------------------------------------------------------------------------
class TestConfigDotEnv:
    """Ensure .env file is respected when present."""

    def test_env_file_values_used(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
        """Config loads values from a .env file in the working directory."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "EMAIL_RECIPIENT=fromdotenv@example.com\n"
            "LOG_LEVEL=DEBUG\n"
            "DRY_RUN=true\n"
        )
        # pydantic-settings reads .env from CWD by default; change into tmp_path
        monkeypatch.chdir(tmp_path)
        config = Config()
        assert config.email_recipient == "fromdotenv@example.com"
        assert config.log_level == "DEBUG"
        assert config.dry_run is True

    def test_env_var_takes_precedence_over_dotenv(
        self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Explicit env vars override .env file values."""
        env_file = tmp_path / ".env"
        env_file.write_text("EMAIL_RECIPIENT=fromdotenv@example.com\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EMAIL_RECIPIENT", "fromenv@example.com")
        config = Config()
        assert config.email_recipient == "fromenv@example.com"
