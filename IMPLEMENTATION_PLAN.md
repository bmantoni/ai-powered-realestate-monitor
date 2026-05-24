# Implementation Plan: Snowshoe Ski Condo Research Bot (Revised)

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runner                     │
│                    (or Local / Container)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────┐  │
│  │   Fetcher    │───▶│  HTML Parser     │───▶│ Storage  │  │
│  │  (fetch raw  │    │ (BeautifulSoup   │    │ (JSON)   │  │
│  │   HTML from  │    │  for known       │    │          │  │
│  │   any URL)   │    │  sources)        │    │          │  │
│  └──────────────┘    └──────────────────┘    └──────────┘  │
│           │                    │                             │
│           │                    ▼                             │
│           │         ┌──────────────────┐                     │
│           │         │  AI Scraper      │                     │
│           │         │  (fallback for   │                     │
│           │         │   new sources)   │                     │
│           │         └──────────────────┘                     │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │   AI Enrichment  │                                        │
│  │  (Gemini/Kimi)   │                                        │
│  └────────┬─────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ Email Generator  │                                        │
│  │  (Jinja2/HTML)   │                                        │
│  └────────┬─────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │  SMTP SendGrid   │                                        │
│  └──────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Key architectural decisions:
- **Hybrid Scraping**: Known sources (firsttracts.com) use fast BeautifulSoup HTML parsers. Unknown sources automatically fall back to AI-powered extraction. Adding a new source is as simple as adding a URL—no code changes needed for AI fallback.
- **AI Enrichment**: View classification and summaries use AI only for properties that pass basic filters, minimizing API costs.
- **JSON Persistence**: Single JSON file for all state storage. Easy for GitHub Actions artifact persistence and simple to inspect locally.
- **Local Testing**: Full support for running locally with live data fetching, with optional email suppression. Reports are saved as HTML files for browser viewing.
- **Pagination**: Automatically follows pagination links to exhaustively fetch all listings.

## 2. Tech Stack

- **Language**: Python 3.11+
- **HTTP**: `httpx` (async-capable, modern replacement for requests)
- **HTML Parsing**: `beautifulsoup4` for fast structured extraction from known sources
- **Data Processing**: `pydantic` for validation
- **Templating**: `jinja2` for HTML email generation
- **Email Delivery**: `sendgrid` (primary; SES and Gmail documented but not yet implemented)
- **AI Integration**: `google-generativeai` (Gemini) or OpenAI-compatible client for Kimi
- **Persistence**: `json` (single file only)
- **Scheduling**: GitHub Actions `schedule` event or local cron
- **Configuration**: `pydantic-settings` with `.env` support
- **Logging**: `loguru` for structured logging

## 3. Data Models

### `Property` (Pydantic Model)
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Property(BaseModel):
    id: str  # Unique identifier (URL hash or extracted ID)
    source: str  # "firsttracts" or future source name
    source_url: str  # The URL this was scraped from
    listing_url: str  # Direct link to the listing
    title: str
    price: float
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    property_name: Optional[str] = None  # "Allegheny Springs" or "Rimfire Lodge"
    location: Optional[str] = None  # "Snowshoe Village" or other
    view_description: Optional[str] = None
    image_urls: list[str] = []
    description: str
    is_available: bool = True
    first_seen: datetime
    last_updated: datetime
    last_price: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_view_classification: Optional[str] = None  # "mountain", "ski_area", "other"
    ai_raw_json: Optional[str] = None  # Store the raw AI extraction response for debugging

class DailySnapshot(BaseModel):
    date: datetime
    total_listings: int
    average_price: float
    median_price: float
    new_listings: list[str]  # IDs
    price_changes: list[str]  # IDs
    removed_listings: list[str]  # IDs

class Config(BaseModel):
    # Sources: list of URLs to scrape
    sources: list[str] = ["https://www.firsttracts.com/real-estate/our-listings"]
    
    # Pagination
    max_pages_per_source: int = 10  # Maximum pages to fetch per source
    
    # Filtering criteria
    allowed_properties: list[str] = ["Allegheny Springs", "Rimfire Lodge"]
    required_location_keywords: list[str] = ["Snowshoe Village", "Snowshoe"]
    min_bedrooms: int = 1
    max_bedrooms: int = 1
    min_price: float = 150000
    max_price: float = 200000
    
    # AI
    ai_provider: str = "gemini"  # "gemini" or "kimi"
    gemini_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    ai_model: Optional[str] = None  # Override default model
    
    # Email
    email_recipient: str
    email_from: str = "snowshoe-bot@example.com"
    smtp_provider: str = "sendgrid"  # "sendgrid" (SES and Gmail documented but not implemented)
    sendgrid_api_key: Optional[str] = None
    
    # Execution mode
    dry_run: bool = False  # If True, fetch and process but don't send email
    skip_ai: bool = False  # If True, skip AI enrichment (faster local testing)
    
    # Persistence
    data_path: str = "./data/properties.json"
    
    # Scheduling
    run_frequency: str = "0 8 * * *"  # Daily at 8 AM
    
    # Logging
    log_level: str = "INFO"
```

## 4. Hybrid Scraping Strategy

The bot uses a two-tier scraping approach:

1. **Fast HTML Parser** – For known sources (firsttracts.com), a source-specific BeautifulSoup parser extracts structured data directly from HTML. This is ~100x faster than AI extraction.
2. **AI Fallback** – For unknown sources, the pipeline automatically falls back to AI-powered extraction via Gemini/Kimi.

### Tier 1: Source-Specific HTML Parser (firsttracts.com)

```python
from bs4 import BeautifulSoup

def parse_listings_html(html: str, source_url: str) -> list[Property]:
    """Parse property listings from firsttracts.com HTML."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    
    for panel in soup.find_all("div", class_="panel"):
        mls_number = panel.get("data-mlsnumber")
        if not mls_number:
            continue
        
        # Extract title, price, bedrooms, etc. from structured HTML
        title = panel.find("h3", class_="panel-title").find("a").get_text(strip=True)
        price = extract_price_from_text(panel.find("span", class_="pull-right").get_text())
        bedrooms = extract_badge_value(panel, "Bedrooms")
        # ... etc
        
        listings.append(Property(...))
    
    return listings
```

### Tier 2: AI-Powered Extraction (Generic Sources)

For unknown sources, the bot falls back to the AI scraper:

```python
class AIScraper:
    def __init__(self, ai_client):
        self.ai = ai_client
    
    async def extract_listings(self, html: str, source_url: str) -> list[Property]:
        prompt = EXTRACTION_PROMPT.format(html=html[:150000])
        response = await self.ai.generate_json(prompt)
        
        listings = []
        for item in response:
            listings.append(Property(
                id=item.get("id") or generate_id_from_url(item["listing_url"]),
                source=extract_source_name(source_url),
                source_url=source_url,
                # ... etc
            ))
        
        return listings
```

### Source Selection in Pipeline

```python
# In pipeline.py:
if "firsttracts.com" in page_url:
    listings = parse_listings_html(listings_html, page_url)
else:
    listings = await self.scraper.extract_listings(listings_html, page_url)
```

### Why Hybrid?

**Pros:**
- **Speed**: Firsttracts.com (primary source) scrapes in ~1 second vs ~90 seconds with AI
- **Cost**: AI only used for view classification (~5 properties) instead of all 133 listings
- **Extensibility**: New sources work automatically via AI fallback
- **Reliability**: Structured HTML parsing is deterministic; no AI hallucinations

**Cons:**
- Source-specific parsers require initial development
- AI fallback costs money for unknown sources
- May need new parser for each new source (if performance matters)

**Mitigations:**
- AI fallback handles new sources without code changes
- Caching for AI responses
- Option to skip AI for faster local testing (`skip_ai` flag)

## 5. JSON Persistence

Single JSON file for all state:

```json
{
  "version": 1,
  "last_run": "2024-01-15T08:00:00Z",
  "properties": {
    "firsttracts_abc123": {
      "id": "firsttracts_abc123",
      "source": "firsttracts",
      "source_url": "https://www.firsttracts.com/real-estate/our-listings",
      "listing_url": "https://www.firsttracts.com/...",
      "title": "Allegheny Springs 1BR",
      "price": 175000,
      "bedrooms": 1,
      "property_name": "Allegheny Springs",
      "location": "Snowshoe Village",
      "view_description": "Mountain view across the valley",
      "image_urls": ["https://..."],
      "description": "Beautiful 1BR condo...",
      "is_available": true,
      "first_seen": "2024-01-10T08:00:00Z",
      "last_updated": "2024-01-15T08:00:00Z",
      "last_price": null,
      "ai_summary": "Cozy 1BR with mountain views",
      "ai_view_classification": "mountain",
      "ai_raw_json": "{...}"
    }
  },
  "snapshots": [
    {
      "date": "2024-01-15T08:00:00Z",
      "total_listings": 5,
      "average_price": 178000,
      "median_price": 175000,
      "new_listings": ["firsttracts_def456"],
      "price_changes": ["firsttracts_abc123"],
      "removed_listings": []
    }
  ]
}
```

### Storage Class
```python
import json
import os
from typing import Dict, List, Optional

class JsonStorage:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._data = self._load()
    
    def _load(self) -> dict:
        if not os.path.exists(self.filepath):
            return {"version": 1, "properties": {}, "snapshots": []}
        with open(self.filepath, 'r') as f:
            return json.load(f)
    
    def save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, 'w') as f:
            json.dump(self._data, f, indent=2, default=str)
    
    def get_property(self, property_id: str) -> Optional[dict]:
        return self._data["properties"].get(property_id)
    
    def upsert_property(self, property_id: str, data: dict):
        existing = self._data["properties"].get(property_id)
        if existing:
            # Track price changes
            if existing.get("price") != data.get("price"):
                data["last_price"] = existing["price"]
            data["first_seen"] = existing["first_seen"]
        self._data["properties"][property_id] = data
    
    def mark_removed(self, active_ids: List[str]):
        for pid, prop in self._data["properties"].items():
            if pid not in active_ids:
                prop["is_available"] = False
    
    def add_snapshot(self, snapshot: dict):
        self._data["snapshots"].append(snapshot)
        # Keep only last 90 days of snapshots
        cutoff = datetime.utcnow() - timedelta(days=90)
        self._data["snapshots"] = [
            s for s in self._data["snapshots"]
            if datetime.fromisoformat(s["date"]) > cutoff
        ]
    
    def get_all_properties(self) -> Dict[str, dict]:
        return self._data["properties"]
    
    def get_latest_snapshot(self) -> Optional[dict]:
        if not self._data["snapshots"]:
            return None
        return self._data["snapshots"][-1]
```

## 6. Filtering Logic

```python
def matches_criteria(property: Property, config: Config) -> bool:
    """Check if property matches user criteria."""
    
    # Price check
    if property.price < config.min_price or property.price > config.max_price:
        return False
    
    # Bedroom check
    if property.bedrooms is not None:
        if property.bedrooms < config.min_bedrooms or property.bedrooms > config.max_bedrooms:
            return False
    
    # Property name check
    if config.allowed_properties:
        if not any(name.lower() in (property.property_name or "").lower() 
                   for name in config.allowed_properties):
            return False
    
    # Location check
    if config.required_location_keywords:
        location_text = f"{property.location or ''} {property.description or ''}".lower()
        if not any(kw.lower() in location_text for kw in config.required_location_keywords):
            return False
    
    # View check (AI classification)
    if property.ai_view_classification:
        if property.ai_view_classification not in ["mountain", "ski_area"]:
            return False
    
    return True
```

## 7. Email Templating

Same Jinja2 approach as original plan, but simplified:

```html
<!-- templates/email.html -->
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; }
        .header { background: #2c5282; color: white; padding: 20px; }
        .metrics { background: #f7fafc; padding: 15px; margin: 20px 0; border-radius: 8px; }
        .listing { border: 1px solid #e2e8f0; margin: 15px 0; padding: 15px; border-radius: 8px; }
        .price-down { color: #38a169; font-weight: bold; }
        .price-up { color: #e53e3e; }
        .new-badge { background: #48bb78; color: white; padding: 2px 8px; border-radius: 4px; }
        .removed { opacity: 0.6; text-decoration: line-through; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        img { max-width: 200px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Snowshoe Condo Daily Report</h1>
        <p>{{ date.strftime("%B %d, %Y") }}</p>
    </div>
    
    <div class="metrics">
        <h2>Market Overview</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Active Listings</td><td>{{ snapshot.total_listings }}</td></tr>
            <tr><td>Average Price</td><td>${{ "{:,.0f}".format(snapshot.average_price) }}</td></tr>
            <tr><td>Median Price</td><td>${{ "{:,.0f}".format(snapshot.median_price) }}</td></tr>
            <tr><td>New Today</td><td>{{ snapshot.new_listings|length }}</td></tr>
            <tr><td>Price Changes</td><td>{{ snapshot.price_changes|length }}</td></tr>
            <tr><td>Removed</td><td>{{ snapshot.removed_listings|length }}</td></tr>
        </table>
    </div>
    
    <h2>Listings</h2>
    {% for property in properties %}
    <div class="listing {% if not property.is_available %}removed{% endif %}">
        {% if property.id in new_ids %}
            <span class="new-badge">NEW</span>
        {% endif %}
        <h3><a href="{{ property.listing_url }}">{{ property.title }}</a></h3>
        {% if property.image_urls %}
            <img src="{{ property.image_urls[0] }}" alt="{{ property.title }}">
        {% endif %}
        <table>
            <tr><td>Price</td>
                <td>
                    ${{ "{:,.0f}".format(property.price) }}
                    {% if property.id in price_changed_ids and property.last_price %}
                        {% if property.price < property.last_price %}
                            <span class="price-down">↓ ${{ "{:,.0f}".format(property.last_price - property.price) }}</span>
                        {% else %}
                            <span class="price-up">↑ ${{ "{:,.0f}".format(property.price - property.last_price) }}</span>
                        {% endif %}
                    {% endif %}
                </td>
            </tr>
            <tr><td>Property</td><td>{{ property.property_name }}</td></tr>
            <tr><td>Bedrooms</td><td>{{ property.bedrooms }}</td></tr>
            <tr><td>View</td><td>{{ property.ai_view_classification or property.view_description }}</td></tr>
        </table>
        {% if property.ai_summary %}
            <p><strong>Summary:</strong> {{ property.ai_summary }}</p>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
```

## 8. AI Integration

### View Classification Prompt
```python
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
```

### Summary Prompt
```python
SUMMARY_PROMPT = """
Summarize this ski condo listing in 1-2 sentences. Focus on the key selling points and view.

Title: {title}
Price: ${price}
Property: {property_name}
Description: {description}
"""
```

## 9. Local Testing Setup

### `.env` for Local Development
```bash
# Required
EMAIL_RECIPIENT=test@example.com
GEMINI_API_KEY=your_key_here

# Optional overrides
DRY_RUN=true              # Set to true to skip sending email
SKIP_AI=false             # Set to true to skip AI (faster, but no view filtering)
DATA_PATH=./data/test-properties.json
LOG_LEVEL=DEBUG

# Sources
SOURCES=https://www.firsttracts.com/real-estate/our-listings
```

### Local Run Command
```bash
# Install dependencies
pip install -r requirements.txt

# Run with live data, no email
DRY_RUN=true python src/main.py

# Run with AI disabled for fast testing
SKIP_AI=true DRY_RUN=true python src/main.py

# Full run with email
python src/main.py
```

### Test Fixtures
Store sample HTML responses in `tests/fixtures/` for unit testing:
```
tests/
├── fixtures/
│   ├── firsttracts_listings.html
│   └── firsttracts_detail.html
├── test_ai_scraper.py
├── test_pipeline.py
└── test_storage.py
```

## 10. File / Module Structure

```
snowshoe-condo-bot/
├── .github/
│   └── workflows/
│       └── daily-report.yml
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Pydantic settings / env vars
│   ├── models.py               # Pydantic data models
│   ├── fetcher.py              # HTTP fetching utilities
│   ├── firsttracts_scraper.py  # Fast HTML parser for firsttracts.com
│   ├── ai_scraper.py           # AI-powered HTML extraction (fallback)
│   ├── ai_client.py            # AI provider abstraction (Gemini/Kimi)
│   ├── ai_enrichment.py        # AI view classification & summaries
│   ├── paginator.py            # Pagination support
│   ├── storage.py              # JSON file persistence
│   ├── filter.py               # Criteria matching logic
│   ├── email_generator.py      # Jinja2 + email composition
│   ├── email_sender.py         # SendGrid delivery
│   ├── utils.py                # Retry & circuit breaker utilities
│   └── pipeline.py             # Orchestration logic
├── templates/
│   └── email.html              # Jinja2 email template
├── data/
│   └── .gitkeep                # State files (gitignored in practice)
├── reports/                    # Generated HTML reports
├── tests/
│   ├── fixtures/               # Sample HTML for testing
│   ├── test_ai_scraper.py
│   ├── test_firsttracts_scraper.py
│   ├── test_paginator.py
│   ├── test_pipeline.py
│   ├── test_storage.py
│   └── test_integration.py
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

## 11. Deployment

### GitHub Actions Workflow
```yaml
name: Daily Snowshoe Condo Report

on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8 AM ET
  workflow_dispatch:      # Allow manual runs

jobs:
  generate-report:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Download previous state
        uses: actions/download-artifact@v4
        with:
          name: property-data
          path: data/
        continue-on-error: true
      
      - name: Run report generator
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          SENDGRID_API_KEY: ${{ secrets.SENDGRID_API_KEY }}
          EMAIL_RECIPIENT: ${{ secrets.EMAIL_RECIPIENT }}
          SOURCES: ${{ secrets.SOURCES }}
        run: python src/main.py
      
      - name: Upload updated state
        uses: actions/upload-artifact@v4
        with:
          name: property-data
          path: data/properties.json
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: execution-logs
          path: logs/
```

### Dockerfile (for home server)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY templates/ ./templates/
COPY data/ ./data/

ENV PYTHONPATH=/app
ENV DATA_PATH=/app/data/properties.json

# Run once and exit (use host cron to schedule)
CMD ["python", "src/main.py"]
```

## 12. Implementation Phases

### Phase 1: Foundation
- [x] Set up project structure
- [x] Implement config with pydantic-settings
- [x] Create data models
- [x] Implement JSON storage
- [x] Set up logging

### Phase 2: Fetching & Scraping
- [x] Implement HTTP fetcher with httpx
- [x] Implement pagination support
- [x] Create firsttracts.com HTML parser (BeautifulSoup)
- [x] Implement AI scraper fallback for new sources
- [x] Test with live firsttracts.com data locally

### Phase 3: Filtering & Pipeline
- [x] Implement criteria matching
- [x] Build diff engine (new/changed/removed)
- [x] Calculate daily metrics
- [x] Test full pipeline locally with DRY_RUN

### Phase 4: AI Enrichment
- [x] Implement view classification
- [x] Implement summary generation
- [x] Test view filtering accuracy

### Phase 5: Email & Deployment
- [x] Create Jinja2 email template
- [x] Implement SendGrid integration
- [x] Add local HTML report generation
- [x] Test email rendering
- [x] Set up GitHub Actions workflow
- [x] Configure secrets

### Phase 6: Polish
- [x] Improve error handling and retries
- [x] Add monitoring for AI costs
- [ ] Add more sources to config
- [ ] Historical metrics visualization (optional)

## 13. Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `EMAIL_RECIPIENT` | Yes | Where to send reports | - |
| `GEMINI_API_KEY` | Yes* | Gemini API key | - |
| `KIMI_API_KEY` | Yes* | Kimi API key | - |
| `SENDGRID_API_KEY` | Yes** | SendGrid API key | - |
| `SOURCES` | No | Comma-separated URLs | `https://www.firsttracts.com/real-estate/our-listings` |
| `ALLOWED_PROPERTIES` | No | Allowed property names | `Allegheny Springs,Rimfire Lodge` |
| `REQUIRED_LOCATION_KEYWORDS` | No | Location keywords | `Snowshoe Village,Snowshoe` |
| `MIN_BEDROOMS` | No | Minimum bedrooms | `1` |
| `MAX_BEDROOMS` | No | Maximum bedrooms | `1` |
| `MIN_PRICE` | No | Minimum price filter | `150000` |
| `MAX_PRICE` | No | Maximum price filter | `200000` |
| `MAX_PAGES_PER_SOURCE` | No | Max pages to fetch per source | `10` |
| `AI_PROVIDER` | No | AI provider (`gemini` or `kimi`) | `gemini` |
| `AI_MODEL` | No | AI model override | `gemini-2.5-flash` |
| `EMAIL_FROM` | No | Sender email address | `snowshoe-bot@example.com` |
| `SMTP_PROVIDER` | No | Email provider (`sendgrid`) | `sendgrid` |
| `DRY_RUN` | No | Skip email sending | `false` |
| `SKIP_AI` | No | Skip AI enrichment | `false` |
| `DATA_PATH` | No | State file path | `./data/properties.json` |
| `RUN_FREQUENCY` | No | Cron expression for scheduling | `0 8 * * *` |
| `LOG_LEVEL` | No | Logging level | `INFO` |

\*At least one AI provider required unless `SKIP_AI=true`
\*\*Only SendGrid is currently implemented; SES and Gmail are documented but not yet available

## 14. Cost Estimation

**HTML Scraping (per run):**
- Firsttracts.com parsing: Free (no AI calls)
- ~14 pages fetched via HTTP

**AI Enrichment (per run):**
- View classification + summary: ~5 matching listings × ~1k tokens ≈ $0.005
- **Total AI cost per run: ~$0.005** (well within Gemini free tier)

**Email:**
- SendGrid free tier: 100 emails/day

**Note:** Unknown sources that fall back to AI scraping will incur higher costs (~$0.02 per page).

## Success Criteria

- [x] Runs daily without manual intervention
- [x] Adding a new source = adding one URL to config (falls back to AI scraper)
- [x] Accurately identifies properties matching ALL criteria
- [x] Correctly detects new listings, price changes, and removals
- [x] Sends well-formatted HTML email with images and metrics
- [x] Generates local HTML reports for browser viewing
- [x] State persists between runs via JSON artifact
- [x] Easily testable locally with live data
- [x] Works with `DRY_RUN=true` for safe testing
- [x] AI correctly classifies views (mountain vs ski area vs other)
- [x] Fetches all pages via automatic pagination
