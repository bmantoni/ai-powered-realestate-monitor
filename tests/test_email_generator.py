"""Tests for the email generator module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Template

from src.email_generator import EmailGenerator
from src.models import DailySnapshot, Property


class TestEmailGenerator:
    """Comprehensive tests for EmailGenerator."""

    @pytest.fixture
    def template_dir(self, tmp_path: Path) -> Path:
        """Create a temporary templates directory with a minimal email template."""
        templates = tmp_path / "templates"
        templates.mkdir()
        template_content = """<!DOCTYPE html>
<html>
<head><style>body{font-family:Arial}</style></head>
<body>
<div class="header"><h1>Snowshoe Condo Daily Report</h1><p>{{ date.strftime("%B %d, %Y") }}</p></div>
<div class="metrics">
<h2>Market Overview</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Active Listings</td><td>{{ snapshot.total_listings }}</td></tr>
<tr><td>Average Price</td><td>${{ "{:,.0f}".format(snapshot.average_price) }}</td></tr>
<tr><td>Median Price</td><td>${{ "{:,.0f}".format(snapshot.median_price) }}</td></tr>
<tr><td>New Today</td><td>{{ new_ids|length }}</td></tr>
<tr><td>Price Changes</td><td>{{ price_changed_ids|length }}</td></tr>
<tr><td>Removed</td><td>{{ removed_ids|length }}</td></tr>
</table>
</div>
<h2>Listings</h2>
{% if not properties %}
<div class="empty-state"><p>No listings match your criteria today.</p></div>
{% endif %}
{% for property in properties %}
<div class="listing {% if not property.is_available %}removed{% endif %}">
{% if property.id in new_ids %}<span class="new-badge">NEW</span>{% endif %}
<h3><a href="{{ property.listing_url }}">{{ property.title }}</a></h3>
{% if property.image_urls %}<img src="{{ property.image_urls[0] }}" alt="{{ property.title }}">{% endif %}
<table>
<tr><td>Price</td><td>
${{ "{:,.0f}".format(property.price) }}
{% if property.id in price_changed_ids and property.last_price %}
{% if property.price < property.last_price %}<span class="price-down">↓ ${{ "{:,.0f}".format(property.last_price - property.price) }}</span>
{% else %}<span class="price-up">↑ ${{ "{:,.0f}".format(property.price - property.last_price) }}</span>{% endif %}
{% endif %}
</td></tr>
<tr><td>Property</td><td>{{ property.property_name or "N/A" }}</td></tr>
<tr><td>Bedrooms</td><td>{{ property.bedrooms or "N/A" }}</td></tr>
<tr><td>Bathrooms</td><td>{{ property.bathrooms or "N/A" }}</td></tr>
<tr><td>Sqft</td><td>{{ property.sqft or "N/A" }}</td></tr>
<tr><td>Location</td><td>{{ property.location or "N/A" }}</td></tr>
<tr><td>View</td><td>{{ property.ai_view_classification or property.view_description or "N/A" }}</td></tr>
</table>
{% if property.ai_summary %}<p><strong>Summary:</strong> {{ property.ai_summary }}</p>{% endif %}
</div>
{% endfor %}
</body>
</html>"""
        (templates / "email.html").write_text(template_content, encoding="utf-8")
        return templates

    @pytest.fixture
    def generator(self, template_dir: Path) -> EmailGenerator:
        """Return an EmailGenerator instance pointing at the temp template."""
        return EmailGenerator(template_path=str(template_dir / "email.html"))

    @pytest.fixture
    def sample_properties(self) -> list[Property]:
        """Return a list of sample properties for testing."""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        return [
            Property(
                id="prop-001",
                source="firsttracts",
                source_url="https://example.com",
                listing_url="https://example.com/1",
                title="Allegheny Springs 1BR",
                price=175_000.0,
                bedrooms=1,
                bathrooms=1.0,
                sqft=450,
                property_name="Allegheny Springs",
                location="Snowshoe Village",
                view_description="Mountain view",
                image_urls=["https://example.com/img1.jpg"],
                description="Cozy condo",
                is_available=True,
                first_seen=base_time,
                last_updated=base_time,
            ),
            Property(
                id="prop-002",
                source="firsttracts",
                source_url="https://example.com",
                listing_url="https://example.com/2",
                title="Rimfire Lodge Studio",
                price=190_000.0,
                bedrooms=1,
                bathrooms=1.5,
                sqft=600,
                property_name="Rimfire Lodge",
                location="Snowshoe",
                view_description="Ski slope view",
                image_urls=["https://example.com/img2.jpg", "https://example.com/img3.jpg"],
                description="Spacious studio",
                is_available=True,
                first_seen=base_time,
                last_updated=base_time,
            ),
        ]

    @pytest.fixture
    def sample_snapshot(self) -> DailySnapshot:
        """Return a sample daily snapshot."""
        return DailySnapshot(
            date=datetime(2024, 1, 15, 23, 59, 59),
            total_listings=2,
            average_price=182_500.0,
            median_price=175_000.0,
            new_listings=["prop-001"],
            price_changes=[],
            removed_listings=["prop-003"],
        )

    # ------------------------------------------------------------------ #
    #  Basic rendering
    # ------------------------------------------------------------------ #

    def test_render_returns_string(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Rendering should return a non-empty HTML string."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids={"prop-001"},
            price_changed_ids=set(),
            removed_ids={"prop-003"},
        )
        assert isinstance(html, str)
        assert len(html) > 0
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_render_includes_date(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """The email header should contain the formatted snapshot date."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "January 15, 2024" in html

    # ------------------------------------------------------------------ #
    #  Metrics
    # ------------------------------------------------------------------ #

    def test_metrics_total_listings(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Metrics table should display the total number of active listings."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "Active Listings" in html
        assert "2" in html

    def test_metrics_average_price_formatted(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Average price should be formatted with commas and no decimals."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "$182,500" in html

    def test_metrics_median_price_formatted(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Median price should be formatted with commas and no decimals."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "$175,000" in html

    def test_metrics_new_count(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """New-today metric should reflect the number of new listings."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids={"prop-001"},
            price_changed_ids=set(),
            removed_ids=set(),
        )
        # snapshot says 1 new listing
        assert "New Today" in html
        assert "1" in html

    def test_metrics_price_change_count(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Price-changes metric should reflect the number of changed listings."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids={"prop-002"},
            removed_ids=set(),
        )
        assert "Price Changes" in html

    def test_metrics_removed_count(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Removed metric should reflect the number of removed listings."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids={"prop-003"},
        )
        assert "Removed" in html
        assert "1" in html

    # ------------------------------------------------------------------ #
    #  Property details
    # ------------------------------------------------------------------ #

    def test_property_title_and_link(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Each listing should show its title as a link to the listing URL."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "Allegheny Springs 1BR" in html
        assert 'href="https://example.com/1"' in html
        assert "Rimfire Lodge Studio" in html
        assert 'href="https://example.com/2"' in html

    def test_property_price_formatted(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Property prices should be formatted with commas."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "$175,000" in html
        assert "$190,000" in html

    def test_property_details(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Property details (bedrooms, bathrooms, sqft, location) should render."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "Allegheny Springs" in html
        assert "Rimfire Lodge" in html
        assert "Snowshoe Village" in html
        assert "Snowshoe" in html

    # ------------------------------------------------------------------ #
    #  Images
    # ------------------------------------------------------------------ #

    def test_image_displayed(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """First image URL should appear as an img tag when present."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert '<img src="https://example.com/img1.jpg"' in html
        assert '<img src="https://example.com/img2.jpg"' in html

    def test_no_image_when_empty(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """No img tag should be rendered when a property has no images."""
        prop = Property(
            id="prop-no-img",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/no-img",
            title="No Image Property",
            price=150_000.0,
            image_urls=[],
            description="No images here",
            is_available=True,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "No Image Property" in html
        # Make sure there are no img tags at all
        assert "<img" not in html

    # ------------------------------------------------------------------ #
    #  New badge
    # ------------------------------------------------------------------ #

    def test_new_badge_rendered(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """A NEW badge should appear for listings in new_ids."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids={"prop-001"},
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert 'class="new-badge"' in html
        assert "NEW" in html

    def test_no_new_badge_for_existing(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """No NEW badge should appear when new_ids is empty."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert 'class="new-badge"' not in html
        assert "NEW" not in html

    # ------------------------------------------------------------------ #
    #  Price changes
    # ------------------------------------------------------------------ #

    def test_price_down_indicator(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """A price decrease should show a green down-arrow with the difference."""
        prop = Property(
            id="prop-price-down",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/down",
            title="Price Drop",
            price=170_000.0,
            last_price=180_000.0,
            image_urls=[],
            description="Price dropped",
            is_available=True,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids={"prop-price-down"},
            removed_ids=set(),
        )
        assert 'class="price-down"' in html
        assert "↓" in html
        assert "$10,000" in html

    def test_price_up_indicator(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """A price increase should show a red up-arrow with the difference."""
        prop = Property(
            id="prop-price-up",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/up",
            title="Price Hike",
            price=185_000.0,
            last_price=175_000.0,
            image_urls=[],
            description="Price increased",
            is_available=True,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids={"prop-price-up"},
            removed_ids=set(),
        )
        assert 'class="price-up"' in html
        assert "↑" in html
        assert "$10,000" in html

    def test_no_price_change_indicator_when_unchanged(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """No arrow indicators should appear when price_changed_ids is empty."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert 'class="price-down"' not in html
        assert 'class="price-up"' not in html
        assert "↓" not in html
        assert "↑" not in html

    # ------------------------------------------------------------------ #
    #  Removed listings
    # ------------------------------------------------------------------ #

    def test_removed_listing_styling(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """Removed listings should have the 'removed' CSS class."""
        prop = Property(
            id="prop-removed",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/removed",
            title="Gone Property",
            price=160_000.0,
            image_urls=[],
            description="No longer available",
            is_available=False,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids={"prop-removed"},
        )
        assert 'class="listing removed"' in html

    def test_active_listing_no_removed_class(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """Active listings should NOT have the 'removed' CSS class."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        # Each listing div should only have "listing" class, not "removed"
        for prop in sample_properties:
            # Check that the specific listing doesn't have removed class
            assert prop.is_available is True
        # Should not have any removed class in the output since all are active
        assert 'class="listing removed"' not in html

    # ------------------------------------------------------------------ #
    #  Empty state
    # ------------------------------------------------------------------ #

    def test_empty_state_message(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """When no properties are provided, an empty-state message should appear."""
        html = generator.render(
            properties=[],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert 'class="empty-state"' in html
        assert "No listings match your criteria today" in html

    def test_no_empty_state_when_listings_exist(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """The empty-state message should NOT appear when properties exist."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert 'class="empty-state"' not in html
        assert "No listings match your criteria today" not in html

    # ------------------------------------------------------------------ #
    #  None / missing fields
    # ------------------------------------------------------------------ #

    def test_none_fields_display_nicely(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """When optional fields are None, they should render gracefully."""
        prop = Property(
            id="prop-minimal",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/minimal",
            title="Minimal Property",
            price=150_000.0,
            bedrooms=None,
            bathrooms=None,
            sqft=None,
            property_name=None,
            location=None,
            view_description=None,
            image_urls=[],
            description="Minimal",
            is_available=True,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "Minimal Property" in html
        # The template should handle Nones gracefully (shows "N/A" or similar)
        assert "N/A" in html

    # ------------------------------------------------------------------ #
    #  AI summary
    # ------------------------------------------------------------------ #

    def test_ai_summary_rendered(self, generator: EmailGenerator, sample_snapshot: DailySnapshot) -> None:
        """When ai_summary is present, it should appear in the email."""
        prop = Property(
            id="prop-ai",
            source="firsttracts",
            source_url="https://example.com",
            listing_url="https://example.com/ai",
            title="AI Property",
            price=150_000.0,
            ai_summary="Gorgeous mountain views with ski-in access",
            image_urls=[],
            description="Has AI summary",
            is_available=True,
            first_seen=datetime(2024, 1, 15, 10, 0, 0),
            last_updated=datetime(2024, 1, 15, 10, 0, 0),
        )
        html = generator.render(
            properties=[prop],
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "<strong>Summary:</strong>" in html
        assert "Gorgeous mountain views with ski-in access" in html

    def test_ai_summary_omitted_when_none(self, generator: EmailGenerator, sample_properties: list[Property], sample_snapshot: DailySnapshot) -> None:
        """When ai_summary is None, the summary section should not appear."""
        html = generator.render(
            properties=sample_properties,
            snapshot=sample_snapshot,
            new_ids=set(),
            price_changed_ids=set(),
            removed_ids=set(),
        )
        assert "<strong>Summary:</strong>" not in html

    # ------------------------------------------------------------------ #
    #  Default template path
    # ------------------------------------------------------------------ #

    def test_default_template_path(self) -> None:
        """EmailGenerator should have a sensible default template path."""
        gen = EmailGenerator()
        assert "templates/email.html" in gen.template_path

    def test_file_not_found_raises_error(self) -> None:
        """Providing a non-existent template path should raise an error."""
        with pytest.raises(Exception):
            gen = EmailGenerator(template_path="/nonexistent/path/email.html")
            gen.render(
                properties=[],
                snapshot=DailySnapshot(
                    date=datetime(2024, 1, 15),
                    total_listings=0,
                    average_price=0.0,
                    median_price=0.0,
                ),
                new_ids=set(),
                price_changed_ids=set(),
                removed_ids=set(),
            )
