"""Pipeline orchestration: fetch → scrape → filter → diff → snapshot → store."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any

from loguru import logger

from src.ai_scraper import AIScraper
from src.config import Config
from src.fetcher import fetch_html
from src.filter import matches_criteria
from src.firsttracts_scraper import parse_listings_html
from src.models import DailySnapshot, Property
from src.paginator import Paginator
from src.storage import JsonStorage


class Pipeline:
    """Orchestrate the end-to-end property research workflow."""

    def __init__(
        self,
        *,
        config: Config,
        storage: JsonStorage,
        scraper: AIScraper,
    ) -> None:
        self.config = config
        self.storage = storage
        self.scraper = scraper

    async def run(self) -> tuple[DailySnapshot, list[Property]]:
        """Execute the full pipeline for all configured sources.

        Returns:
            A tuple of ``(daily_snapshot, relevant_properties)``.
        """
        all_properties: list[Property] = []

        # ------------------------------------------------------------------
        # 1. Fetch & extract from every source (with pagination)
        # ------------------------------------------------------------------
        paginator = Paginator(max_pages=self.config.max_pages_per_source)
        for source_url in self.config.sources:
            try:
                pages = await paginator.fetch_all_pages(source_url)
                for page_url, html in pages:
                    # Some sites (like firsttracts.com) return AJAX responses
                    # split by "~~" into [listings_html, count, pagination]
                    if "~~" in html:
                        parts = html.split("~~")
                        listings_html = parts[0] if parts else html
                        logger.debug(
                            "Parsed AJAX response for {}: {} parts, listings HTML is {} chars",
                            page_url,
                            len(parts),
                            len(listings_html),
                        )
                    else:
                        listings_html = html
                    
                    # Use source-specific parser when available, fallback to AI scraper
                    if "firsttracts.com" in page_url:
                        listings = parse_listings_html(listings_html, page_url)
                    else:
                        listings = await self.scraper.extract_listings(listings_html, page_url)
                    logger.info(
                        "Extracted {} listings from {}",
                        len(listings),
                        page_url,
                    )
                    all_properties.extend(listings)
            except Exception as exc:
                logger.warning("Source {} failed: {}", source_url, exc)
                continue

        all_fetched_ids = {p.id for p in all_properties}

        # ------------------------------------------------------------------
        # 2. Diff baseline (before we mutate storage)
        # ------------------------------------------------------------------
        # Deep-copy so that subsequent upserts do not alter our baseline.
        previously_stored = {
            pid: dict(p) for pid, p in self.storage.get_all_properties().items()
        }
        previously_available = {
            pid
            for pid, p in previously_stored.items()
            if p.get("is_available", True)
        }

        # ------------------------------------------------------------------
        # 3. Update storage with everything we fetched
        # ------------------------------------------------------------------
        for prop in all_properties:
            self.storage.upsert_property(prop.id, prop.model_dump())

        self.storage.mark_removed(list(all_fetched_ids))

        # ------------------------------------------------------------------
        # 4. Filter to user-relevant subset
        # ------------------------------------------------------------------
        relevant = [p for p in all_properties if matches_criteria(p, self.config)]

        # ------------------------------------------------------------------
        # 5. Detect changes *among relevant properties*
        # ------------------------------------------------------------------
        new_listings = [
            p.id for p in relevant if p.id not in previously_stored
        ]
        price_changes = [
            p.id
            for p in relevant
            if p.id in previously_stored
            and previously_stored[p.id].get("price") != p.price
        ]
        removed_listings = [
            pid for pid in previously_available if pid not in all_fetched_ids
        ]

        # ------------------------------------------------------------------
        # 6. Calculate daily metrics
        # ------------------------------------------------------------------
        total_listings = len(relevant)
        if relevant:
            prices = [p.price for p in relevant]
            average_price = sum(prices) / len(prices)
            median_price = median(prices)
        else:
            average_price = 0.0
            median_price = 0.0

        snapshot = DailySnapshot(
            date=datetime.now(timezone.utc),
            total_listings=total_listings,
            average_price=average_price,
            median_price=median_price,
            new_listings=new_listings,
            price_changes=price_changes,
            removed_listings=removed_listings,
        )

        # ------------------------------------------------------------------
        # 7. Update last_run timestamp
        # ------------------------------------------------------------------
        self.storage.set_last_run(datetime.now(timezone.utc).isoformat())

        # ------------------------------------------------------------------
        # 8. Persist
        # ------------------------------------------------------------------
        self.storage.add_snapshot(snapshot.model_dump())
        self.storage.save()

        return snapshot, relevant
