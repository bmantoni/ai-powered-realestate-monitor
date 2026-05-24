"""Updated tests for src.main — full orchestration, CLI args, and error handling."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.models import DailySnapshot, Property


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_property() -> Property:
    """Return a sample Property for use in pipeline mocks."""
    return Property(
        id="test-001",
        source="firsttracts",
        source_url="https://example.com",
        listing_url="https://example.com/1",
        title="Allegheny Springs 1BR",
        price=175_000.0,
        bedrooms=1,
        property_name="Allegheny Springs",
        location="Snowshoe Village",
        description="Cozy condo",
        is_available=True,
        first_seen=datetime(2024, 1, 15, 10, 0, 0),
        last_updated=datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def sample_snapshot() -> DailySnapshot:
    """Return a sample DailySnapshot."""
    return DailySnapshot(
        date=datetime(2024, 1, 15, 10, 0, 0),
        total_listings=1,
        average_price=175_000.0,
        median_price=175_000.0,
        new_listings=["test-001"],
        price_changes=[],
        removed_listings=[],
    )


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with sensible defaults."""
    config = MagicMock(spec=Config)
    config.sources = ["https://example.com/listings"]
    config.dry_run = False
    config.skip_ai = False
    config.log_level = "INFO"
    config.data_path = "./data/test-properties.json"
    config.email_recipient = "test@example.com"
    config.email_from = "bot@example.com"
    config.smtp_provider = "sendgrid"
    config.sendgrid_api_key = "SG.test"
    config.ai_provider = "gemini"
    config.gemini_api_key = "gemini-test"
    config.kimi_api_key = None
    config.ai_model = None
    config.allowed_properties = ["Allegheny Springs", "Rimfire Lodge"]
    config.required_location_keywords = ["Snowshoe"]
    config.min_bedrooms = 1
    config.max_bedrooms = 1
    config.min_price = 150_000.0
    config.max_price = 200_000.0
    config.run_frequency = "0 8 * * *"
    return config


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestCLIArgumentParsing:
    """Tests for parse_args() helper."""

    def test_parse_args_no_arguments(self):
        """parse_args with no arguments should return all False/None defaults."""
        from src.main import parse_args

        args = parse_args([])
        assert args.dry_run is False
        assert args.skip_ai is False
        assert args.sources is None
        assert args.data_path is None
        assert args.log_level is None

    def test_parse_args_dry_run(self):
        """--dry-run should set dry_run to True."""
        from src.main import parse_args

        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_parse_args_skip_ai(self):
        """--skip-ai should set skip_ai to True."""
        from src.main import parse_args

        args = parse_args(["--skip-ai"])
        assert args.skip_ai is True

    def test_parse_args_sources(self):
        """--sources should accept multiple URLs."""
        from src.main import parse_args

        args = parse_args(["--sources", "https://a.com", "https://b.com"])
        assert args.sources == ["https://a.com", "https://b.com"]

    def test_parse_args_data_path(self):
        """--data-path should set the data path."""
        from src.main import parse_args

        args = parse_args(["--data-path", "/tmp/data.json"])
        assert args.data_path == "/tmp/data.json"

    def test_parse_args_log_level(self):
        """--log-level should set the log level."""
        from src.main import parse_args

        args = parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_parse_args_combined(self):
        """Multiple flags should all be parsed correctly."""
        from src.main import parse_args

        args = parse_args([
            "--dry-run",
            "--skip-ai",
            "--sources", "https://a.com",
            "--data-path", "/tmp/test.json",
            "--log-level", "DEBUG",
        ])
        assert args.dry_run is True
        assert args.skip_ai is True
        assert args.sources == ["https://a.com"]
        assert args.data_path == "/tmp/test.json"
        assert args.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Config building
# ---------------------------------------------------------------------------


class TestBuildConfig:
    """Tests for build_config() helper."""

    @patch("src.main.Config")
    def test_build_config_no_overrides(self, mock_config_cls: MagicMock) -> None:
        """When no CLI args are provided, config should use defaults."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        mock_config.dry_run = False
        mock_config.skip_ai = False
        args = parse_args([])
        config = build_config(args)

        assert config is mock_config
        assert config.dry_run is False
        assert config.skip_ai is False

    @patch("src.main.Config")
    def test_build_config_overrides_dry_run(self, mock_config_cls: MagicMock) -> None:
        """CLI --dry-run should override config.dry_run."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        args = parse_args(["--dry-run"])
        config = build_config(args)

        assert config.dry_run is True

    @patch("src.main.Config")
    def test_build_config_overrides_skip_ai(self, mock_config_cls: MagicMock) -> None:
        """CLI --skip-ai should override config.skip_ai."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        args = parse_args(["--skip-ai"])
        config = build_config(args)

        assert config.skip_ai is True

    @patch("src.main.Config")
    def test_build_config_overrides_sources(self, mock_config_cls: MagicMock) -> None:
        """CLI --sources should override config.sources."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        args = parse_args(["--sources", "https://a.com", "https://b.com"])
        config = build_config(args)

        assert config.sources == ["https://a.com", "https://b.com"]

    @patch("src.main.Config")
    def test_build_config_overrides_data_path(self, mock_config_cls: MagicMock) -> None:
        """CLI --data-path should override config.data_path."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        args = parse_args(["--data-path", "/tmp/test.json"])
        config = build_config(args)

        assert config.data_path == "/tmp/test.json"

    @patch("src.main.Config")
    def test_build_config_overrides_log_level(self, mock_config_cls: MagicMock) -> None:
        """CLI --log-level should override config.log_level."""
        from src.main import build_config, parse_args

        mock_config = mock_config_cls.return_value
        args = parse_args(["--log-level", "DEBUG"])
        config = build_config(args)

        assert config.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Component initialization
# ---------------------------------------------------------------------------


class TestComponentInitialization:
    """Tests that run_bot() initializes all components correctly."""

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_initializes_storage_with_data_path(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """JsonStorage should be initialized with config.data_path."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))

        await run_bot(mock_config)

        mock_storage_cls.assert_called_once_with(mock_config.data_path)

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_creates_ai_client_with_config(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """AI client should be created with the config."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))

        await run_bot(mock_config)

        mock_create_ai.assert_called_once_with(mock_config)

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_initializes_pipeline_with_components(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """Pipeline should be initialized with config, storage, and scraper."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_storage = mock_storage_cls.return_value
        mock_scraper = mock_scraper_cls.return_value

        await run_bot(mock_config)

        mock_pipeline_cls.assert_called_once_with(
            config=mock_config,
            storage=mock_storage,
            scraper=mock_scraper,
        )

    @patch("src.main.EmailSender")
    @patch("src.main._save_html_report")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_initializes_email_sender_with_config(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """EmailSender should be initialized with config."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))

        await run_bot(mock_config)

        mock_email_sender_cls.assert_called_once_with(mock_config)


# ---------------------------------------------------------------------------
# Full pipeline execution
# ---------------------------------------------------------------------------


class TestPipelineExecution:
    """Tests for the full execution flow in run_bot()."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_runs_pipeline_and_returns_zero(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """run_bot should execute the pipeline and return 0 on success."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>email</html>"

        result = await run_bot(mock_config)

        assert result == 0
        mock_pipeline.run.assert_awaited_once()

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_enriches_properties_when_skip_ai_false(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """When skip_ai=False, properties should be enriched."""
        from src.main import run_bot

        mock_config.skip_ai = False
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        enriched_prop = sample_property.model_copy()
        enriched_prop.ai_summary = "Great condo!"
        mock_enricher.enrich_properties = AsyncMock(return_value=[enriched_prop])

        await run_bot(mock_config)

        mock_enricher.enrich_properties.assert_awaited_once()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main._save_html_report")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_skips_enrichment_when_skip_ai_true(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """When skip_ai=True, enrichment should be skipped."""
        from src.main import run_bot

        mock_config.skip_ai = True
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value

        await run_bot(mock_config)

        mock_enricher.enrich_properties.assert_not_called()

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_generates_email_with_pipeline_results(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """Email should be generated with snapshot, properties, and change sets."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value

        await run_bot(mock_config)

        mock_email_gen.render.assert_called_once()
        call_kwargs = mock_email_gen.render.call_args[1]
        assert call_kwargs["snapshot"] == sample_snapshot
        assert call_kwargs["properties"] == [sample_property]
        assert call_kwargs["new_ids"] == set(sample_snapshot.new_listings)
        assert call_kwargs["price_changed_ids"] == set(sample_snapshot.price_changes)
        assert call_kwargs["removed_ids"] == set(sample_snapshot.removed_listings)

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_sends_email_when_not_dry_run(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """In normal mode, email should be sent via EmailSender."""
        from src.main import run_bot

        mock_config.dry_run = False
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>test</html>"
        mock_email_sender = mock_email_sender_cls.return_value

        await run_bot(mock_config)

        mock_email_sender.send_email.assert_called_once()
        call_args = mock_email_sender.send_email.call_args
        assert call_args[1]["html_content"] == "<html>test</html>"
        assert "Snowshoe Condo Daily Report" in call_args[1]["subject"]

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_skips_email_when_dry_run(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """In dry-run mode, email should not be sent."""
        from src.main import run_bot

        mock_config.dry_run = True
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>test</html>"
        mock_email_sender = mock_email_sender_cls.return_value

        await run_bot(mock_config)

        mock_email_sender.send_email.assert_not_called()

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_saves_html_report_locally(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
        tmp_path: Path,
    ) -> None:
        """HTML report should be saved to a file for local viewing."""
        from src.main import _save_html_report, run_bot

        mock_config.dry_run = True
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>test report</html>"

        # Override reports dir to tmp_path
        with patch("src.main.Path") as mock_path_cls:
            mock_path_cls.return_value = tmp_path
            mock_path_cls.__truediv__ = lambda self, other: tmp_path / other
            
            await run_bot(mock_config)
        
        # Verify the report was saved
        report_file = tmp_path / "snowshoe-report-2024-01-15.html"
        assert report_file.exists()
        assert report_file.read_text() == "<html>test report</html>"

    def test_save_html_report_creates_file(self, tmp_path: Path) -> None:
        """_save_html_report should write HTML to a timestamped file."""
        from src.main import _save_html_report

        with patch("src.main.Path") as mock_path_cls:
            reports_dir = tmp_path / "reports"
            mock_path_cls.return_value = reports_dir
            mock_path_cls.__truediv__ = lambda self, other: reports_dir / other
            
            result = _save_html_report("<html>test</html>", datetime(2024, 1, 15, 10, 0, 0))
        
        assert result.name == "snowshoe-report-2024-01-15.html"
        assert result.read_text() == "<html>test</html>"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in run_bot()."""

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_pipeline_failure_returns_nonzero(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """If the pipeline fails, run_bot should return a non-zero exit code."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(side_effect=RuntimeError("Pipeline exploded"))

        result = await run_bot(mock_config)

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
    async def test_email_failure_logs_error_but_returns_zero(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """If email sending fails, the error should be logged but execution continues."""
        from src.main import run_bot

        mock_config.dry_run = False
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>test</html>"
        mock_email_sender = mock_email_sender_cls.return_value
        mock_email_sender.send_email.side_effect = RuntimeError("SMTP down")

        result = await run_bot(mock_config)

        assert result == 0
        mock_logger.error.assert_called()
        error_calls = [str(c) for c in mock_logger.error.call_args_list]
        assert any("email" in c.lower() for c in error_calls)

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_enrichment_failure_continues_with_unenriched(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """If enrichment fails, email should still be sent with unenriched properties."""
        from src.main import run_bot

        mock_config.skip_ai = False
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(side_effect=RuntimeError("AI down"))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>test</html>"
        mock_email_sender = mock_email_sender_cls.return_value

        result = await run_bot(mock_config)

        assert result == 0
        mock_email_gen.render.assert_called_once()
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
    async def test_empty_properties_generates_email(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_config: MagicMock,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """Even with zero properties, an email should be generated and sent."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, []))
        mock_email_gen = mock_email_gen_cls.return_value
        mock_email_gen.render.return_value = "<html>empty</html>"
        mock_email_sender = mock_email_sender_cls.return_value

        await run_bot(mock_config)

        mock_email_gen.render.assert_called_once()
        mock_email_sender.send_email.assert_called_once()


# ---------------------------------------------------------------------------
# Logging and metrics
# ---------------------------------------------------------------------------


class TestLoggingAndMetrics:
    """Tests for execution logging and metrics."""

    @patch("src.main.EmailSender")
    @patch("src.main._save_html_report")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_logs_execution_time(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """run_bot should log the total execution time."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])

        await run_bot(mock_config)

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("execution time" in c.lower() or "completed in" in c.lower() for c in info_calls)

    @patch("src.main._save_html_report")
    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_logs_property_counts(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """run_bot should log counts of fetched, filtered, and enriched properties."""
        from src.main import run_bot

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])

        await run_bot(mock_config)

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("fetched" in c.lower() or "filtered" in c.lower() or "listings" in c.lower() for c in info_calls)

    @patch("src.main.EmailSender")
    @patch("src.main.EmailGenerator")
    @patch("src.main.AIEnricher")
    @patch("src.main.AIScraper")
    @patch("src.main.create_ai_client")
    @patch("src.main._save_html_report")
    @patch("src.main.JsonStorage")
    @patch("src.main.Pipeline")
    @patch("src.main.logger")
    @pytest.mark.asyncio
    async def test_logs_ai_costs_when_ai_used(
        self,
        mock_logger: MagicMock,
        mock_pipeline_cls: MagicMock,
        mock_storage_cls: MagicMock,
        mock_create_ai: MagicMock,
        mock_scraper_cls: MagicMock,
        mock_enricher_cls: MagicMock,
        mock_email_gen_cls: MagicMock,
        mock_email_sender_cls: MagicMock,
        mock_save_report: MagicMock,
        mock_config: MagicMock,
        sample_property: Property,
        sample_snapshot: DailySnapshot,
    ) -> None:
        """run_bot should log AI call counts when AI is used."""
        from src.main import run_bot

        mock_config.skip_ai = False
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run = AsyncMock(return_value=(sample_snapshot, [sample_property]))
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.total_calls = 4
        mock_enricher.enrich_properties = AsyncMock(return_value=[sample_property])

        await run_bot(mock_config)

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("ai" in c.lower() or "enrichment" in c.lower() for c in info_calls)


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


class TestMainEntryPoint:
    """Tests for the main() synchronous entry point."""

    @patch("src.main.asyncio.run")
    @patch("src.main.setup_logging")
    @patch("src.main.build_config")
    @patch("src.main.parse_args")
    def test_main_calls_asyncio_run(
        self,
        mock_parse_args: MagicMock,
        mock_build_config: MagicMock,
        mock_setup_logging: MagicMock,
        mock_asyncio_run: MagicMock,
    ) -> None:
        """main() should use asyncio.run() to execute the async bot logic."""
        from src.main import main

        mock_parse_args.return_value = MagicMock()
        mock_build_config.return_value = MagicMock()
        mock_asyncio_run.return_value = 0

        result = main([])

        assert result == 0
        mock_asyncio_run.assert_called_once()

    @patch("src.main.run_bot")
    @patch("src.main.setup_logging")
    @patch("src.main.build_config")
    @patch("src.main.parse_args")
    def test_main_passes_config_to_run_bot(
        self,
        mock_parse_args: MagicMock,
        mock_build_config: MagicMock,
        mock_setup_logging: MagicMock,
        mock_run_bot: MagicMock,
    ) -> None:
        """main() should pass the built config to run_bot via asyncio.run."""
        from src.main import main

        mock_config = MagicMock()
        mock_parse_args.return_value = MagicMock()
        mock_build_config.return_value = mock_config
        mock_run_bot.return_value = 0

        main([])

        # asyncio.run(run_bot(config)) — so run_bot should be the coroutine passed
        # We patch run_bot itself and check it's called with config inside asyncio.run
        # Since we patch asyncio.run, we verify the coroutine arg is correct by checking
        # that run_bot was awaited or passed correctly. With our patch, we check mock_run_bot.
        # Actually asyncio.run receives a coroutine object, so we need to verify differently.
        # Let's instead test that the coroutine was created with the right config.
        # A simpler approach: check that build_config output is used.
        call_args = mock_run_bot.call_args
        assert call_args is not None
        assert call_args[0][0] is mock_config

    @patch("src.main.logger")
    @patch("src.main.asyncio.run")
    @patch("src.main.setup_logging")
    @patch("src.main.build_config")
    @patch("src.main.parse_args")
    def test_main_keyboard_interrupt_returns_130(
        self,
        mock_parse_args: MagicMock,
        mock_build_config: MagicMock,
        mock_setup_logging: MagicMock,
        mock_asyncio_run: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """main() should return 130 on KeyboardInterrupt (standard SIGINT exit code)."""
        from src.main import main

        mock_parse_args.return_value = MagicMock()
        mock_build_config.return_value = MagicMock()
        mock_asyncio_run.side_effect = KeyboardInterrupt()

        result = main([])

        assert result == 130
        mock_logger.info.assert_any_call("Interrupted by user, shutting down gracefully")

    @patch("src.main.logger")
    @patch("src.main.asyncio.run")
    @patch("src.main.setup_logging")
    @patch("src.main.build_config")
    @patch("src.main.parse_args")
    def test_main_unexpected_error_returns_1(
        self,
        mock_parse_args: MagicMock,
        mock_build_config: MagicMock,
        mock_setup_logging: MagicMock,
        mock_asyncio_run: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """main() should return 1 on unexpected errors during setup."""
        from src.main import main

        mock_parse_args.return_value = MagicMock()
        mock_build_config.side_effect = RuntimeError("Config error")

        result = main([])

        assert result == 1
        mock_logger.exception.assert_called()
