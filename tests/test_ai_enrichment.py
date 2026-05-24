"""Tests for AI enrichment module."""

from __future__ import annotations

import pytest
from datetime import datetime

from src.ai_client import MockAIClient
from src.ai_enrichment import AIEnricher
from src.config import Config
from src.models import Property


@pytest.fixture
def mock_ai_client():
    """Return a fresh MockAIClient."""
    return MockAIClient()


@pytest.fixture
def enricher(mock_ai_client: MockAIClient) -> AIEnricher:
    """Return an AIEnricher with skip_ai=False."""
    config = Config(email_recipient="test@example.com", skip_ai=False)
    return AIEnricher(ai_client=mock_ai_client, config=config)


@pytest.fixture
def skip_enricher(mock_ai_client: MockAIClient) -> AIEnricher:
    """Return an AIEnricher with skip_ai=True."""
    config = Config(email_recipient="test@example.com", skip_ai=True)
    return AIEnricher(ai_client=mock_ai_client, config=config)


@pytest.fixture
def sample_property() -> Property:
    """Return a sample Property for testing."""
    return Property(
        id="test-001",
        source="firsttracts",
        source_url="https://example.com/listings",
        listing_url="https://example.com/1",
        title="Cozy Condo at Allegheny Springs",
        price=175_000.0,
        bedrooms=1,
        bathrooms=1.0,
        sqft=450,
        property_name="Allegheny Springs",
        location="Snowshoe Village",
        view_description="Mountain view across the valley",
        image_urls=["https://example.com/img1.jpg"],
        description="Beautiful 1BR condo with mountain views.",
        is_available=True,
        first_seen=datetime(2024, 1, 15, 10, 0, 0),
        last_updated=datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def ski_property() -> Property:
    """Return a sample Property with ski area description."""
    return Property(
        id="test-002",
        source="firsttracts",
        source_url="https://example.com/listings",
        listing_url="https://example.com/2",
        title="Ski-in Ski-out at Rimfire",
        price=190_000.0,
        bedrooms=1,
        bathrooms=1.0,
        sqft=500,
        property_name="Rimfire Lodge",
        location="Snowshoe Village",
        view_description="Slopeside view",
        image_urls=["https://example.com/img2.jpg"],
        description="Direct ski slope views from your balcony.",
        is_available=True,
        first_seen=datetime(2024, 1, 15, 10, 0, 0),
        last_updated=datetime(2024, 1, 15, 10, 0, 0),
    )


# =============================================================================
# View Classification Tests
# =============================================================================


@pytest.mark.asyncio
async def test_classify_view_ski_area(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should return 'ski_area' when AI responds with ski_area."""
    mock_ai_client.set_text_response("ski_area")
    result = await enricher.classify_view("Direct view of ski slopes")
    assert result == "ski_area"


@pytest.mark.asyncio
async def test_classify_view_mountain(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should return 'mountain' when AI responds with mountain."""
    mock_ai_client.set_text_response("mountain")
    result = await enricher.classify_view("Mountain view across the valley")
    assert result == "mountain"


@pytest.mark.asyncio
async def test_classify_view_other(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should return 'other' when AI responds with other."""
    mock_ai_client.set_text_response("other")
    result = await enricher.classify_view("Forest view with trees")
    assert result == "other"


@pytest.mark.asyncio
async def test_classify_view_with_whitespace(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should strip whitespace from AI response."""
    mock_ai_client.set_text_response("  ski_area  ")
    result = await enricher.classify_view("Some description")
    assert result == "ski_area"


@pytest.mark.asyncio
async def test_classify_view_different_case(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should normalize case to lowercase."""
    mock_ai_client.set_text_response("Ski_Area")
    result = await enricher.classify_view("Some description")
    assert result == "ski_area"


@pytest.mark.asyncio
async def test_classify_view_mixed_case_whitespace(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should handle both mixed case and whitespace."""
    mock_ai_client.set_text_response("  Mountain  ")
    result = await enricher.classify_view("Some description")
    assert result == "mountain"


@pytest.mark.asyncio
async def test_classify_view_unexpected_response(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should default to 'other' for unexpected AI responses."""
    mock_ai_client.set_text_response("forest")
    result = await enricher.classify_view("Some description")
    assert result == "other"


@pytest.mark.asyncio
async def test_classify_view_empty_response(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """classify_view should default to 'other' for empty AI response."""
    mock_ai_client.set_text_response("")
    result = await enricher.classify_view("Some description")
    assert result == "other"


@pytest.mark.asyncio
async def test_classify_view_includes_description_in_prompt(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """classify_view should include the description in the prompt sent to AI."""
    mock_ai_client.set_text_response("mountain")
    description = "Gorgeous mountain vista overlooking the valley"
    await enricher.classify_view(description)
    assert description in mock_ai_client.last_prompt


# =============================================================================
# Summary Generation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_generate_summary(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """generate_summary should return AI-generated summary text."""
    expected_summary = "Cozy 1BR with stunning mountain views. Great value at $175,000."
    mock_ai_client.set_text_response(expected_summary)
    result = await enricher.generate_summary(
        title="Cozy Condo",
        price=175_000.0,
        property_name="Allegheny Springs",
        description="Beautiful condo with mountain views.",
    )
    assert result == expected_summary


@pytest.mark.asyncio
async def test_generate_summary_includes_all_fields_in_prompt(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """generate_summary should include title, price, property_name, and description in prompt."""
    mock_ai_client.set_text_response("summary")
    await enricher.generate_summary(
        title="Test Title",
        price=150_000.0,
        property_name="Test Property",
        description="Test description here.",
    )
    prompt = mock_ai_client.last_prompt
    assert "Test Title" in prompt
    assert "150000" in prompt or "150,000" in prompt or "$150000" in prompt
    assert "Test Property" in prompt
    assert "Test description here." in prompt


@pytest.mark.asyncio
async def test_generate_summary_empty_description(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """generate_summary should handle empty description gracefully."""
    mock_ai_client.set_text_response("Affordable condo at Allegheny Springs.")
    result = await enricher.generate_summary(
        title="Cozy Condo",
        price=175_000.0,
        property_name="Allegheny Springs",
        description="",
    )
    assert result == "Affordable condo at Allegheny Springs."


@pytest.mark.asyncio
async def test_generate_summary_short_description(enricher: AIEnricher, mock_ai_client: MockAIClient):
    """generate_summary should handle very short descriptions."""
    mock_ai_client.set_text_response("Nice condo.")
    result = await enricher.generate_summary(
        title="Cozy Condo",
        price=175_000.0,
        property_name="Allegheny Springs",
        description="Hi",
    )
    assert result == "Nice condo."


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_classify_view_ai_error_raises(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """classify_view should raise when AI client fails."""
    mock_ai_client.set_side_effect(RuntimeError("AI service unavailable"))
    with pytest.raises(RuntimeError, match="AI service unavailable"):
        await enricher.classify_view("Some description")


@pytest.mark.asyncio
async def test_generate_summary_ai_error_raises(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """generate_summary should raise when AI client fails."""
    mock_ai_client.set_side_effect(RuntimeError("AI service unavailable"))
    with pytest.raises(RuntimeError, match="AI service unavailable"):
        await enricher.generate_summary(
            title="Cozy Condo",
            price=175_000.0,
            property_name="Allegheny Springs",
            description="Beautiful condo.",
        )


@pytest.mark.asyncio
async def test_enrich_property_error_returns_unchanged(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """enrich_property should return property unchanged when AI fails."""
    mock_ai_client.set_side_effect(RuntimeError("AI service unavailable"))
    original = sample_property.model_copy()
    result = await enricher.enrich_property(sample_property)
    assert result.ai_view_classification is None
    assert result.ai_summary is None
    assert result.id == original.id
    assert result.price == original.price


@pytest.mark.asyncio
async def test_enrich_property_classification_error_returns_unchanged(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """enrich_property should return unchanged if classification fails."""
    original_call_count = 0
    async def failing_then_success(prompt: str) -> str:
        nonlocal original_call_count
        original_call_count += 1
        if original_call_count == 1:
            raise RuntimeError("Classification failed")
        return "Summary text"
    
    mock_ai_client.generate_text = failing_then_success
    result = await enricher.enrich_property(sample_property)
    assert result.ai_view_classification is None
    assert result.ai_summary is None


# =============================================================================
# Enrich Property Tests
# =============================================================================


@pytest.mark.asyncio
async def test_enrich_property_sets_both_fields(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """enrich_property should set both ai_view_classification and ai_summary."""
    call_count = 0

    async def sequential_response(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "mountain"
        return "Cozy 1BR with mountain views."

    mock_ai_client.generate_text = sequential_response
    result = await enricher.enrich_property(sample_property)
    assert result.ai_view_classification == "mountain"
    assert result.ai_summary == "Cozy 1BR with mountain views."


@pytest.mark.asyncio
async def test_enrich_property_does_not_mutate_original_id(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """enrich_property should preserve all original property fields."""
    mock_ai_client.set_text_response("other")
    result = await enricher.enrich_property(sample_property)
    assert result.id == sample_property.id
    assert result.title == sample_property.title
    assert result.price == sample_property.price
    assert result.description == sample_property.description
    assert result.source == sample_property.source


# =============================================================================
# Batch Enrichment Tests
# =============================================================================


@pytest.mark.asyncio
async def test_enrich_properties_batch(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property, ski_property: Property
):
    """enrich_properties should enrich multiple properties."""
    responses = ["mountain", "Summary 1", "ski_area", "Summary 2"]
    idx = 0

    async def sequential_response(prompt: str) -> str:
        nonlocal idx
        response = responses[idx]
        idx += 1
        return response

    mock_ai_client.generate_text = sequential_response
    results = await enricher.enrich_properties([sample_property, ski_property])
    assert len(results) == 2
    assert results[0].ai_view_classification == "mountain"
    assert results[0].ai_summary == "Summary 1"
    assert results[1].ai_view_classification == "ski_area"
    assert results[1].ai_summary == "Summary 2"


@pytest.mark.asyncio
async def test_enrich_properties_batch_continues_on_error(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property, ski_property: Property
):
    """enrich_properties should continue processing if one property fails."""
    call_count = 0

    async def failing_then_success(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First property's classify_view fails
            raise RuntimeError("AI error")
        if call_count == 2:  # Second property's classify_view
            return "ski_area"
        return "Summary 2"  # Second property's generate_summary (call 3)

    mock_ai_client.generate_text = failing_then_success
    results = await enricher.enrich_properties([sample_property, ski_property])
    assert len(results) == 2
    # First property should be unchanged due to error
    assert results[0].ai_view_classification is None
    assert results[0].ai_summary is None
    # Second property should be enriched
    assert results[1].ai_view_classification == "ski_area"
    assert results[1].ai_summary == "Summary 2"


@pytest.mark.asyncio
async def test_enrich_properties_empty_list(enricher: AIEnricher):
    """enrich_properties should return empty list for empty input."""
    results = await enricher.enrich_properties([])
    assert results == []


# =============================================================================
# Skip AI Tests
# =============================================================================


@pytest.mark.asyncio
async def test_skip_ai_flag_property_returns_unchanged(
    skip_enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """When skip_ai=True, enrich_property should return property unchanged without calling AI."""
    result = await skip_enricher.enrich_property(sample_property)
    assert result.ai_view_classification is None
    assert result.ai_summary is None
    assert mock_ai_client.call_count == 0


@pytest.mark.asyncio
async def test_skip_ai_flag_properties_returns_all_unchanged(
    skip_enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property, ski_property: Property
):
    """When skip_ai=True, enrich_properties should return all properties unchanged without calling AI."""
    results = await skip_enricher.enrich_properties([sample_property, ski_property])
    assert len(results) == 2
    assert results[0].ai_view_classification is None
    assert results[0].ai_summary is None
    assert results[1].ai_view_classification is None
    assert results[1].ai_summary is None
    assert mock_ai_client.call_count == 0


# =============================================================================
# Cost Tracking Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cost_tracking_counts_calls(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """AIEnricher should track the number of AI calls made."""
    mock_ai_client.set_text_response("mountain")
    await enricher.classify_view("description")
    assert enricher.total_calls == 1
    await enricher.generate_summary("Title", 100_000.0, "Prop", "Desc")
    assert enricher.total_calls == 2


@pytest.mark.asyncio
async def test_cost_tracking_counts_errors(
    enricher: AIEnricher, mock_ai_client: MockAIClient
):
    """AIEnricher should count calls even when they fail."""
    mock_ai_client.set_side_effect(RuntimeError("AI error"))
    with pytest.raises(RuntimeError):
        await enricher.classify_view("description")
    assert enricher.total_calls == 1
    with pytest.raises(RuntimeError):
        await enricher.generate_summary("Title", 100_000.0, "Prop", "Desc")
    assert enricher.total_calls == 2


@pytest.mark.asyncio
async def test_cost_tracking_batch_enrichment(
    enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property, ski_property: Property
):
    """AIEnricher should track calls during batch enrichment (2 properties × 2 calls each = 4)."""
    idx = 0
    responses = ["mountain", "Summary 1", "ski_area", "Summary 2"]

    async def sequential_response(prompt: str) -> str:
        nonlocal idx
        response = responses[idx]
        idx += 1
        return response

    mock_ai_client.generate_text = sequential_response
    await enricher.enrich_properties([sample_property, ski_property])
    assert enricher.total_calls == 4


@pytest.mark.asyncio
async def test_cost_tracking_skip_ai_no_calls(
    skip_enricher: AIEnricher, mock_ai_client: MockAIClient, sample_property: Property
):
    """When skip_ai=True, no calls should be counted."""
    await skip_enricher.enrich_property(sample_property)
    assert skip_enricher.total_calls == 0
