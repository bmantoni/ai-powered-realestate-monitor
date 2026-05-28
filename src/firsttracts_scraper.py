"""Fast HTML scraper for firsttracts.com that parses listings directly.

This replaces the AI-based scraper with direct BeautifulSoup parsing,
which is ~100x faster and more reliable for structured sites.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

from src.models import Property


def _make_absolute(url: str, base_url: str) -> str:
    """Resolve a possibly-relative *url* against *base_url*."""
    if not url:
        return url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme:
        return url
    return urllib.parse.urljoin(base_url, url)


def _extract_source_name(source_url: str) -> str:
    """Derive a short source identifier from a URL hostname."""
    parsed = urllib.parse.urlparse(source_url)
    netloc = parsed.netloc or "unknown"
    name = re.sub(r"^www\.", "", netloc)
    name = name.split(".")[0]
    return name


def _parse_price(price_text: str) -> float | None:
    """Extract numeric price from text like '$169,900'."""
    match = re.search(r'\$([\d,]+)', price_text)
    if match:
        return float(match.group(1).replace(',', ''))
    return None


def _extract_badge_value(panel: BeautifulSoup, label: str) -> int | None:
    """Extract a numeric value from a badge next to a label.
    
    Looks for: <span class="badge">1</span> <b>Bedrooms</b>
    """
    # Find the list-group-item containing the label
    for li in panel.find_all("li", class_="list-group-item"):
        text = li.get_text()
        if label in text:
            badge = li.find("span", class_="badge")
            if badge:
                try:
                    return int(badge.get_text(strip=True))
                except ValueError:
                    return None
    return None


def _extract_quick_fact(panel: BeautifulSoup, label: str) -> str | None:
    """Extract a value from the quick-facts table.
    
    Looks for: <b>Label:</b> Value<br/>
    """
    # Find all quick-facts tds, skip the header one
    quick_facts_tds = panel.find_all("td", class_="quick-facts")
    quick_facts = None
    for td in quick_facts_tds:
        if "quick-facts-header" not in td.get("class", []):
            quick_facts = td
            break
    
    if not quick_facts:
        return None
    
    # Get all text and split by <br/>
    html_str = str(quick_facts)
    # Split by <br> or <br/>
    parts = re.split(r'<br\s*/?>', html_str, flags=re.IGNORECASE)
    
    for part in parts:
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', part)
        clean = clean.strip()
        if clean.startswith(f"{label}:"):
            value = clean[len(label)+1:].strip()
            return value if value else None
    
    return None


def _extract_description(panel: BeautifulSoup) -> str:
    """Extract description text from the panel."""
    desc_li = panel.find("li", class_="brdescription")
    if desc_li:
        # Get text, removing the "Description:" label
        text = desc_li.get_text(separator=' ', strip=True)
        text = re.sub(r'^Description:\s*', '', text, flags=re.IGNORECASE)
        # Remove "Read More" link text
        text = re.sub(r'\s*Read More\s*$', '', text, flags=re.IGNORECASE)
        return text
    return ""


def parse_listings_html(html: str, source_url: str) -> list[Property]:
    """Parse property listings from firsttracts.com HTML.
    
    Args:
        html: HTML content containing property panels.
        source_url: The URL the HTML was fetched from.
        
    Returns:
        A list of Property models.
    """
    soup = BeautifulSoup(html, "html.parser")
    source_name = _extract_source_name(source_url)
    now = datetime.now(timezone.utc)
    listings: list[Property] = []
    
    # Find all property panels
    panels = soup.find_all("div", class_="panel")
    
    if not panels:
        logger.warning(
            "No .panel elements found in HTML from {}. HTML sample (first 800 chars): {}",
            source_url,
            html[:800].replace('\n', ' '),
        )
        return []
    
    for panel in panels:
        # Skip non-property panels (like pagination panels)
        mls_number = panel.get("data-mlsnumber")
        if not mls_number:
            continue
        
        # Extract title and URL from panel heading
        title_link = panel.find("h3", class_="panel-title")
        if not title_link:
            continue
        
        title_a = title_link.find("a")
        if not title_a:
            continue
        
        title = title_a.get_text(strip=True)
        listing_url = _make_absolute(title_a.get("href", ""), source_url)
        
        # Extract price
        price_span = title_link.find("span", class_="pull-right")
        price = None
        if price_span:
            price = _parse_price(price_span.get_text())
        
        if not price:
            logger.warning("Skipping listing {} - no price found", mls_number)
            continue
        
        # Extract bedrooms and bathrooms
        bedrooms = _extract_badge_value(panel, "Bedrooms")
        bathrooms = _extract_badge_value(panel, "Bathrooms")
        
        # Extract image URLs
        image_urls = []
        prop_image = panel.find("div", class_="prop-image")
        if prop_image:
            img = prop_image.find("img")
            if img:
                img_src = img.get("src", "")
                if img_src:
                    image_urls.append(_make_absolute(img_src, source_url))
        
        # Extract property name from quick facts
        property_name = _extract_quick_fact(panel, "Snowshoe - On Mt.")
        
        # Normalize property names (site uses abbreviations)
        if property_name:
            property_name_lower = property_name.lower()
            if "rimfire" in property_name_lower:
                property_name = "Rimfire Lodge"
            elif "mt. lodge" in property_name_lower or property_name_lower == "mountain lodge":
                property_name = "Mountain Lodge"
            elif "allegheny" in property_name_lower:
                property_name = "Allegheny Springs"
            elif "highland" in property_name_lower:
                property_name = "Highland House"
            elif "snowcrest" in property_name_lower:
                property_name = "Snowcrest"
        
        if not property_name:
            # Try to extract from title (e.g., "256 Rimfire Lodge")
            # Look for known property names in the title
            title_lower = title.lower()
            if "allegheny" in title_lower:
                property_name = "Allegheny Springs"
            elif "rimfire" in title_lower:
                property_name = "Rimfire Lodge"
            elif "mountain lodge" in title_lower:
                property_name = "Mountain Lodge"
            elif "highland house" in title_lower:
                property_name = "Highland House"
            elif "snowcrest" in title_lower:
                property_name = "Snowcrest"
        
        # Extract location
        location = _extract_quick_fact(panel, "City / Zip")
        if not location:
            location = _extract_quick_fact(panel, "Address")
        
        # Extract description
        description = _extract_description(panel)
        
        prop = Property(
            id=str(mls_number),
            source=source_name,
            source_url=source_url,
            listing_url=listing_url,
            title=title,
            price=price,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            sqft=None,  # Not available in the listing cards
            property_name=property_name,
            location=location,
            view_description=None,  # Will be filled by AI enrichment
            image_urls=image_urls,
            description=description,
            is_available=True,
            first_seen=now,
            last_updated=now,
            ai_raw_json=None,  # No AI involved in scraping
        )
        listings.append(prop)
    
    return listings
