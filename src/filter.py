"""Property filtering logic based on user configuration criteria."""

from __future__ import annotations

from src.config import Config
from src.models import Property


def matches_criteria(property: Property, config: Config) -> bool:
    """Return *True* if *property* satisfies every active filter in *config*.

    Checks are applied in the following order:

    1. **Price** – ``min_price`` ≤ price ≤ ``max_price``.
    2. **Bedrooms** – if known, ``min_bedrooms`` ≤ bedrooms ≤ ``max_bedrooms``.
    3. **Property name** – if ``allowed_properties`` is non-empty, the
       property's ``property_name`` must contain at least one allowed name
       (case-insensitive substring match).
    4. **Location keywords** – if ``required_location_keywords`` is non-empty,
       at least one keyword must appear in the combined location + description
       text (case-insensitive).
    5. **AI view classification** – if the property has been classified by AI,
       only ``"mountain"`` and ``"ski_area"`` are accepted.  A value of
       ``None`` skips this check.
    """
    # Price check
    if property.price < config.min_price or property.price > config.max_price:
        return False

    # Bedroom check
    if property.bedrooms is not None:
        if (
            property.bedrooms < config.min_bedrooms
            or property.bedrooms > config.max_bedrooms
        ):
            return False

    # Property name check
    if config.allowed_properties:
        prop_name = (property.property_name or "").lower()
        if not any(name.lower() in prop_name for name in config.allowed_properties):
            return False

    # Location / keyword check
    if config.required_location_keywords:
        location_text = f"{property.location or ''} {property.description or ''}".lower()
        if not any(kw.lower() in location_text for kw in config.required_location_keywords):
            return False

    # AI view classification check
    if property.ai_view_classification:
        if property.ai_view_classification not in ("mountain", "ski_area"):
            return False

    return True
