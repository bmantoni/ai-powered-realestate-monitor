"""Entry point for the Snowshoe Ski Condo Research Bot.

Orchestrates the full workflow: fetch → scrape → filter → enrich → diff → email.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai_client import AIClient, GeminiAIClient, MockAIClient
from src.ai_enrichment import AIEnricher
from src.config import Config
from src.email_generator import EmailGenerator
from src.email_sender import EmailSender
from src.models import DailySnapshot, Property
from src.pipeline import Pipeline
from src.storage import JsonStorage


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed namespace with optional overrides for config values.
    """
    parser = argparse.ArgumentParser(
        description="Snowshoe Ski Condo Research Bot — daily property monitoring and reporting."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and process but do not send email.",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip AI enrichment (faster local testing).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Override listing source URLs.",
    )
    parser.add_argument(
        "--data-path",
        default=None,
        help="Override JSON storage file path.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> Config:
    """Build a Config instance, applying CLI overrides.

    Args:
        args: Parsed CLI arguments.

    Returns:
        A Config with environment defaults overridden by CLI flags.
    """
    config = Config()
    if args.dry_run:
        config.dry_run = True
    if args.skip_ai:
        config.skip_ai = True
    if args.sources is not None:
        config.sources = list(args.sources)
    if args.data_path is not None:
        config.data_path = args.data_path
    if args.log_level is not None:
        config.log_level = args.log_level
    return config


def setup_logging(config: Config) -> None:
    """Configure loguru with stderr and file handlers.

    Args:
        config: Application config containing ``log_level``.
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        "logs/snowshoe-bot.log",
        rotation="1 day",
        retention="7 days",
        level=config.log_level,
    )


def _save_html_report(html: str, date: datetime) -> Path:
    """Save the HTML report to disk for local viewing.

    Args:
        html: Full HTML email content.
        date: Report date (used in filename).

    Returns:
        Path to the saved file.
    """
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"snowshoe-report-{date.strftime('%Y-%m-%d')}.html"
    filepath = reports_dir / filename
    filepath.write_text(html, encoding="utf-8")
    return filepath


def create_ai_client(config: Config) -> AIClient:
    """Create an AI client based on configuration.

    Args:
        config: Application configuration.

    Returns:
        An AIClient implementation.
    """
    if config.ai_provider == "gemini" and config.gemini_api_key:
        logger.info("Using Gemini AI client")
        return GeminiAIClient(config.gemini_api_key, config.ai_model)
    elif config.ai_provider == "kimi" and config.kimi_api_key:
        logger.info("Using Kimi AI client (not yet implemented)")
        # TODO: Implement Kimi client
        return MockAIClient()
    else:
        logger.warning(
            "No AI API key configured (provider={}). Using mock client.",
            config.ai_provider,
        )
        return MockAIClient()


async def run_bot(config: Config) -> int:
    """Execute the full async bot workflow.

    Args:
        config: Application configuration.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    start_time = time.monotonic()

    logger.info("Snowshoe Ski Condo Research Bot starting up")
    logger.info(
        "Config: sources={sources}, dry_run={dry_run}, skip_ai={skip_ai}",
        sources=config.sources,
        dry_run=config.dry_run,
        skip_ai=config.skip_ai,
    )

    # ------------------------------------------------------------------
    # 1. Initialise components
    # ------------------------------------------------------------------
    storage = JsonStorage(config.data_path)
    logger.info("Storage initialised at {} — {} properties tracked", config.data_path, len(storage.get_all_properties()))

    ai_client = create_ai_client(config)
    enricher = AIEnricher(ai_client, config)
    pipeline = Pipeline(config=config, storage=storage)
    email_gen = EmailGenerator()
    email_sender = EmailSender(config)

    # ------------------------------------------------------------------
    # 2. Run pipeline: fetch → scrape → filter → diff → store
    # ------------------------------------------------------------------
    try:
        snapshot, properties = await pipeline.run()
    except Exception as exc:
        logger.error("Pipeline failed: {}", exc)
        return 1

    logger.info(
        "Pipeline complete: {} listings fetched, {} relevant after filtering",
        snapshot.total_listings,
        len(properties),
    )

    # ------------------------------------------------------------------
    # 3. AI enrichment (optional)
    # ------------------------------------------------------------------
    if not config.skip_ai:
        try:
            properties = await enricher.enrich_properties(properties)
            logger.info("AI enrichment complete — {} AI calls made", enricher.total_calls)
        except Exception as exc:
            logger.error("AI enrichment failed: {} — continuing with unenriched properties", exc)
            # properties already holds the unenriched list from pipeline.run()
    else:
        logger.info("AI enrichment skipped (--skip-ai)")

    # Persist any enriched data back to storage
    for prop in properties:
        storage.upsert_property(prop.id, prop.model_dump())
    storage.save()

    # ------------------------------------------------------------------
    # 4. Generate email
    # ------------------------------------------------------------------
    new_ids = set(snapshot.new_listings)
    price_changed_ids = set(snapshot.price_changes)
    removed_ids = set(snapshot.removed_listings)

    try:
        html = email_gen.render(
            properties=properties,
            snapshot=snapshot,
            new_ids=new_ids,
            price_changed_ids=price_changed_ids,
            removed_ids=removed_ids,
        )
    except Exception as exc:
        logger.error("Email generation failed: {}", exc)
        return 1

    subject = f"Snowshoe Condo Daily Report - {snapshot.date.strftime('%B %d, %Y')}"

    # ------------------------------------------------------------------
    # 5. Send email (unless dry run)
    # ------------------------------------------------------------------
    report_path = _save_html_report(html, snapshot.date)
    logger.info("Report saved to {}", report_path)

    if not config.dry_run:
        try:
            email_sender.send_email(html_content=html, subject=subject)
            logger.info("Email sent successfully to {}", config.email_recipient)
        except Exception as exc:
            logger.error("Email sending failed: {}", exc)
            # Continue — we still want to exit 0 since data was processed
    else:
        logger.info("DRY RUN — email not sent. Open {} to view the report.", report_path)

    # ------------------------------------------------------------------
    # 6. Log execution metrics
    # ------------------------------------------------------------------
    elapsed = time.monotonic() - start_time
    logger.info(
        "Execution metrics: time={:.2f}s, fetched={}, filtered={}, new={}, price_changes={}, removed={}",
        elapsed,
        snapshot.total_listings,
        len(properties),
        len(snapshot.new_listings),
        len(snapshot.price_changes),
        len(snapshot.removed_listings),
    )
    logger.info(
        "Snowshoe Ski Condo Research Bot finished — execution time: {:.2f}s",
        elapsed,
    )

    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point.

    Parses CLI arguments, builds configuration, sets up logging, and
    delegates to the async ``run_bot()`` coroutine.

    Args:
        argv: Optional argument list override.

    Returns:
        Process exit code.
    """
    try:
        args = parse_args(argv)
        config = build_config(args)
        setup_logging(config)
        return asyncio.run(run_bot(config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down gracefully")
        return 130
    except Exception:
        logger.exception("Unhandled error during startup")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
