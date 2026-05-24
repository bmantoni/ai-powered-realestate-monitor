"""Integration tests for the full Snowshoe bot workflow."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.models import DailySnapshot, Property
from src.storage import JsonStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_config(tmp_path: Path) -> Config:
    """Return a Config suitable for integration tests."""
    return Config(
        email_recipient="test@example.com",
        sources=["https://example.com/src1", "https://example.com/src2"],
        min_price=150_000.0,
        max_price=200_000.0,
        min_bedrooms=1,
        max_bedrooms=1,
        allowed_properties=["Allegheny Springs", "Rimfire Lodge"],
        required_location_keywords=["Snowshoe"],
        data_path=str(tmp_path / "integration-test.json"),
        dry_run=True,
        skip_ai=False,
        sendgrid_api_key="SG.test",
    )


@pytest.fixture
def make_property():
    """Factory for creating Property instances."""
    def _factory(**kwargs: Any) -> Property:
        defaults = {
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
            "is_available": True,
            "first_seen": datetime(2024, 1, 1, 10, 0, 0),
            "last_updated": datetime(2024, 1, 1, 10, 0, 0),
        }
        defaults.update(kwargs)
        return Property(**defaults)
    return _factory


# ---------------------------------------------------------------------------
# End-to-end with mocked external services
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full workflow tests with all external dependencies mocked."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_full_flow_with_two_sources(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """The bot should fetch from multiple sources, enrich, and email."""
        from src.main import run_bot

        prop1 = make_property(id="src1-a", price=160_000.0, property_name="Allegheny Springs")
        prop2 = make_property(id="src2-b", price=190_000.0, property_name="Rimfire Lodge")
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=2,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["src1-a", "src2-b"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop1, prop2]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[prop1, prop2])
        mock_enricher.total_calls = 4
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        result = await run_bot(integration_config)

        assert result == 0
        mock_pipeline.run.assert_awaited_once()
        mock_enricher.enrich_properties.assert_awaited_once()
        mock_email_gen.render.assert_called_once()
        # dry_run=True so email should not be sent
        mock_email_sender_cls.return_value.send_email.assert_not_called()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_full_flow_sends_email_when_not_dry_run(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """When dry_run=False, the bot should send the email."""
        from src.main import run_bot

        integration_config.dry_run = False
        prop = make_property(id="p1", price=175_000.0)
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["p1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[prop])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"
        mock_email_sender = mock_email_sender_cls.return_value

        result = await run_bot(integration_config)

        assert result == 0
        mock_email_sender.send_email.assert_called_once()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_enriched_properties_used_in_email(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """Email should be generated with AI-enriched property data."""
        from src.main import run_bot

        prop = make_property(id="p1", price=175_000.0)
        enriched = prop.model_copy()
        enriched.ai_summary = "Gorgeous mountain views"
        enriched.ai_view_classification = "mountain"
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["p1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[enriched])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        await run_bot(integration_config)

        call_kwargs = mock_email_gen.render.call_args[1]
        assert call_kwargs["properties"][0].ai_summary == "Gorgeous mountain views"
        assert call_kwargs["properties"][0].ai_view_classification == "mountain"


# ---------------------------------------------------------------------------
# Multiple sources handling
# ---------------------------------------------------------------------------


class TestMultipleSources:
    """Tests specifically for multi-source aggregation."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_three_sources_all_succeed(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        tmp_path: Path,
        make_property: Any,
    ) -> None:
        """Bot should handle three sources and aggregate all listings."""
        from src.main import run_bot

        config = Config(
            email_recipient="test@example.com",
            sources=[
                "https://source-a.com",
                "https://source-b.com",
                "https://source-c.com",
            ],
            data_path=str(tmp_path / "multi-source.json"),
            dry_run=True,
            skip_ai=True,
        )

        props = [
            make_property(id="a-1", price=150_000.0, source="source-a"),
            make_property(id="b-1", price=175_000.0, source="source-b"),
            make_property(id="c-1", price=200_000.0, source="source-c"),
        ]
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=3,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["a-1", "b-1", "c-1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, props))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        result = await run_bot(config)

        assert result == 0
        mock_pipeline.run.assert_awaited_once()
        call_kwargs = mock_email_gen.render.call_args[1]
        assert len(call_kwargs["properties"]) == 3


# ---------------------------------------------------------------------------
# Error recovery
# ---------------------------------------------------------------------------


class TestErrorRecovery:
    """Tests for graceful error recovery scenarios."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_pipeline_raises_but_error_is_logged(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
    ) -> None:
        """If the pipeline raises an exception, run_bot should log and return non-zero."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(side_effect=RuntimeError("Network failure"))

        result = await run_bot(integration_config)

        assert result != 0
        mock_logger.error.assert_called()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_one_source_fails_pipeline_returns_partial_results(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """If one source fails during pipeline execution, partial results should still be processed."""
        from src.main import run_bot

        prop = make_property(id="survivor", price=175_000.0)
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["survivor"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        result = await run_bot(integration_config)

        assert result == 0
        mock_email_gen.render.assert_called_once()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_email_send_failure_does_not_crash_bot(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """If email sending fails, the bot should log the error and return 0."""
        from src.main import run_bot

        integration_config.dry_run = False
        prop = make_property(id="p1", price=175_000.0)
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["p1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[prop])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"
        mock_email_sender = mock_email_sender_cls.return_value
        mock_email_sender.send_email.side_effect = RuntimeError("SMTP error")

        result = await run_bot(integration_config)

        assert result == 0
        mock_logger.error.assert_called()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_ai_enrichment_failure_continues_with_plain_properties(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        integration_config: Config,
        make_property: Any,
    ) -> None:
        """If AI enrichment fails, the bot should continue with unenriched properties."""
        from src.main import run_bot

        integration_config.skip_ai = False
        prop = make_property(id="p1", price=175_000.0)
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["p1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(side_effect=RuntimeError("AI timeout"))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        result = await run_bot(integration_config)

        assert result == 0
        mock_email_gen.render.assert_called_once()
        # Properties passed to email should be the original unenriched ones
        call_kwargs = mock_email_gen.render.call_args[1]
        assert call_kwargs["properties"][0].ai_summary is None


# ---------------------------------------------------------------------------
# Storage persistence integration
# ---------------------------------------------------------------------------


class TestStoragePersistence:
    """Tests verifying storage interactions during integration."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_storage_file_is_created(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        tmp_path: Path,
        make_property: Any,
    ) -> None:
        """After running the bot, the storage file should exist on disk."""
        from src.main import run_bot

        data_path = str(tmp_path / "persisted.json")
        config = Config(
            email_recipient="test@example.com",
            sources=["https://example.com"],
            data_path=data_path,
            dry_run=True,
            skip_ai=True,
        )

        prop = make_property(id="p1", price=175_000.0)
        snapshot = DailySnapshot(
            date=datetime.utcnow(),
            total_listings=1,
            average_price=175_000.0,
            median_price=175_000.0,
            new_listings=["p1"],
            price_changes=[],
            removed_listings=[],
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(snapshot, [prop]))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>report</html>"

        result = await run_bot(config)

        assert result == 0
        assert Path(data_path).exists()
