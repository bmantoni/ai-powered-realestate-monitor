"""AI enrichment module for property view classification and summary generation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ai_client import AIClient
    from src.config import Config
    from src.models import Property

logger = logging.getLogger(__name__)

VIEW_PROMPT = """
Analyze this property description and determine the view type for a condo in Snowshoe, WV ski resort.

Description: {description}

The user wants a view that is either:
1. Facing the mountains on the opposite side of the ski area (across the parking lot)
2. Directly facing the ski area/slopes

Classify the view as ONE of:
- "ski_area": Directly faces the ski slopes/runs
- "mountain": Faces mountains on opposite side (across parking lot/valley)
- "other": Forest, parking lot, building interior, or unclear

Respond with ONLY the classification word.
"""

SUMMARY_PROMPT = """
Summarize this ski condo listing in 1-2 sentences. Focus on the key selling points and view.

Title: {title}
Price: ${price}
Property: {property_name}
Description: {description}
"""

VALID_VIEW_CLASSIFICATIONS = {"ski_area", "mountain", "other"}


class AIEnricher:
    """Enriches Property models with AI-generated view classification and summaries."""

    def __init__(self, ai_client: AIClient, config: Config) -> None:
        self.ai_client = ai_client
        self.config = config
        self.total_calls = 0

    async def classify_view(self, description: str) -> str:
        """Classify the view type from a property description.

        Args:
            description: The property description to analyze.

        Returns:
            One of "ski_area", "mountain", or "other".

        Raises:
            Exception: If the AI client fails (propagated to caller).
        """
        prompt = VIEW_PROMPT.format(description=description or "")
        self.total_calls += 1
        response = await self.ai_client.generate_text(prompt)
        cleaned = response.strip().lower()
        if cleaned in VALID_VIEW_CLASSIFICATIONS:
            return cleaned
        logger.warning(f"Unexpected view classification from AI: '{response}'. Defaulting to 'other'.")
        return "other"

    async def generate_summary(
        self, title: str, price: float, property_name: str, description: str
    ) -> str:
        """Generate a 1-2 sentence summary of a property listing.

        Args:
            title: The listing title.
            price: The listing price.
            property_name: The property complex name.
            description: The full property description.

        Returns:
            A 1-2 sentence summary.

        Raises:
            Exception: If the AI client fails (propagated to caller).
        """
        prompt = SUMMARY_PROMPT.format(
            title=title or "",
            price=price,
            property_name=property_name or "",
            description=description or "",
        )
        self.total_calls += 1
        response = await self.ai_client.generate_text(prompt)
        return response.strip()

    async def enrich_property(self, property: Property) -> Property:
        """Enrich a single property with AI classification and summary.

        Args:
            property: The Property to enrich.

        Returns:
            The enriched Property, or the original unchanged if skip_ai is True
            or if the AI client fails.
        """
        if self.config.skip_ai:
            return property

        try:
            view = await self.classify_view(property.description)
            summary = await self.generate_summary(
                title=property.title,
                price=property.price,
                property_name=property.property_name or "",
                description=property.description,
            )
            property.ai_view_classification = view
            property.ai_summary = summary
        except Exception as exc:
            logger.warning(f"AI enrichment failed for property {property.id}: {exc}")

        return property

    async def enrich_properties(self, properties: list[Property]) -> list[Property]:
        """Enrich multiple properties, continuing on individual failures.

        Args:
            properties: List of Property objects to enrich.

        Returns:
            List of enriched (or unchanged) Property objects.
        """
        if self.config.skip_ai:
            return list(properties)

        results = []
        for prop in properties:
            try:
                enriched = await self.enrich_property(prop)
                results.append(enriched)
            except Exception as exc:
                logger.warning(f"AI enrichment failed for property {prop.id}: {exc}")
                results.append(prop)
        return results
