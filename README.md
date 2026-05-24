# Snowshoe Ski Condo Research Bot

A Python bot that scrapes real-estate listings for ski condos at Snowshoe, WV, filters them by your criteria, and sends a daily HTML email report with new listings, price changes, and market metrics.

## Architecture

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   Fetcher    │───▶│  HTML Parser     │───▶│   Storage    │
│  (httpx)     │    │ (BeautifulSoup)  │    │  (JSON File) │
└──────────────┘    └──────────────────┘    └──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   AI Enrichment  │
                    │  (Gemini/Kimi)   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Email Generator  │
                    │  (Jinja2/HTML)   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  SMTP SendGrid   │
                    └──────────────────┘
```

Key decisions:
- **Hybrid Scraping** – Firsttracts.com uses a fast BeautifulSoup HTML parser. Unknown sources automatically fall back to AI-powered extraction, so adding a new source is as simple as adding a URL.
- **AI Enrichment** – View classification and summaries use Gemini (or Kimi) only for properties that match basic criteria, minimizing API costs.
- **JSON Persistence** – A single JSON file stores all state, making it trivial to persist across GitHub Actions runs via artifacts.
- **Local Testing** – Full local execution with live data; emails can be suppressed via `DRY_RUN=true`. Reports are also saved as HTML files for browser viewing.
- **Pagination** – Automatically follows pagination links to fetch all listings across multiple pages.

## Tech Stack

- **Python 3.11+**
- **HTTP** – `httpx`
- **HTML Parsing** – `beautifulsoup4`
- **Validation** – `pydantic` / `pydantic-settings`
- **Templating** – `jinja2`
- **Email** – `sendgrid`
- **AI** – `google-generativeai` (Gemini)
- **Logging** – `loguru`

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd snowshoe-condo-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file (see `.env.example` for all options):

```bash
# Required
EMAIL_RECIPIENT=you@example.com
GEMINI_API_KEY=your_key_here

# Required for email delivery
SENDGRID_API_KEY=your_sendgrid_key

# Optional
DRY_RUN=true              # Set to true to skip sending email
SKIP_AI=false             # Skip AI enrichment for faster local testing
DATA_PATH=./data/properties.json
LOG_LEVEL=INFO
MAX_PAGES_PER_SOURCE=10   # How many pages to fetch per source
```

### 3. Run locally

```bash
# Test run with live data but no email
DRY_RUN=true python -m src.main

# Fast test without AI
SKIP_AI=true DRY_RUN=true python -m src.main

# Full run with email
python -m src.main
```

After running, check the generated report:
```bash
open reports/snowshoe-report-$(date +%Y-%m-%d).html
```

## Configuration

All settings are controlled via environment variables (or `.env`):

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `EMAIL_RECIPIENT` | **Yes** | Where to send reports | — |
| `GEMINI_API_KEY` | Yes* | Gemini API key | — |
| `KIMI_API_KEY` | Yes* | Kimi API key | — |
| `SENDGRID_API_KEY` | Yes** | SendGrid API key | — |
| `SOURCES` | No | Comma-separated URLs | `https://www.firsttracts.com/real-estate/our-listings` |
| `ALLOWED_PROPERTIES` | No | Allowed property names | `Allegheny Springs,Rimfire Lodge` |
| `REQUIRED_LOCATION_KEYWORDS` | No | Location keywords | `Snowshoe Village,Snowshoe` |
| `MIN_BEDROOMS` | No | Minimum bedrooms | `1` |
| `MAX_BEDROOMS` | No | Maximum bedrooms | `1` |
| `MIN_PRICE` | No | Minimum price filter | `150000` |
| `MAX_PRICE` | No | Maximum price filter | `200000` |
| `MAX_PAGES_PER_SOURCE` | No | Max pages per source | `10` |
| `AI_PROVIDER` | No | AI provider | `gemini` |
| `AI_MODEL` | No | AI model override | `gemini-2.5-flash` |
| `EMAIL_FROM` | No | Sender email | `snowshoe-bot@example.com` |
| `SMTP_PROVIDER` | No | Email provider | `sendgrid` |
| `DRY_RUN` | No | Skip email sending | `false` |
| `SKIP_AI` | No | Skip AI enrichment | `false` |
| `DATA_PATH` | No | State file path | `./data/properties.json` |
| `RUN_FREQUENCY` | No | Cron expression | `0 8 * * *` |
| `LOG_LEVEL` | No | Logging level | `INFO` |

\*At least one AI provider is required unless `SKIP_AI=true`.
\*\*Required for email delivery (only SendGrid is currently implemented).

## Deployment

### GitHub Actions (Recommended)

1. Push this repository to GitHub.
2. Add the following secrets in **Settings → Secrets and variables → Actions**:
   - `GEMINI_API_KEY`
   - `SENDGRID_API_KEY`
   - `EMAIL_RECIPIENT`
   - `SOURCES` (optional)
3. The workflow (`.github/workflows/daily-report.yml`) runs daily at 8 AM ET and uploads the JSON state as an artifact for persistence.

### Docker (Home Server)

Build and run:

```bash
docker build -t snowshoe-bot .
docker run --rm \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e SENDGRID_API_KEY=$SENDGRID_API_KEY \
  -e EMAIL_RECIPIENT=$EMAIL_RECIPIENT \
  -e DRY_RUN=false \
  -v $(pwd)/data:/app/data \
  snowshoe-bot
```

For scheduled runs, add to your host's `crontab`:

```cron
0 8 * * * docker run --rm -e GEMINI_API_KEY=... -e SENDGRID_API_KEY=... snowshoe-bot
```

## Project Structure

```
snowshoe-condo-bot/
├── .github/workflows/daily-report.yml   # CI/CD schedule
├── src/
│   ├── __init__.py
│   ├── main.py                          # Entry point
│   ├── config.py                        # Pydantic settings
│   ├── models.py                        # Property & Snapshot models
│   ├── fetcher.py                       # HTTP fetching
│   ├── firsttracts_scraper.py           # Fast HTML parser for firsttracts.com
│   ├── ai_scraper.py                    # AI-powered extraction (fallback)
│   ├── ai_client.py                     # AI provider abstraction
│   ├── ai_enrichment.py                 # View classification & summaries
│   ├── paginator.py                     # Pagination support
│   ├── storage.py                       # JSON persistence
│   ├── filter.py                        # Criteria matching
│   ├── email_generator.py               # Jinja2 HTML rendering
│   ├── email_sender.py                  # SendGrid delivery
│   └── utils.py                         # Retry & circuit breaker utilities
├── templates/
│   └── email.html                       # Email template
├── data/
│   └── .gitkeep                         # State files
├── reports/                             # Generated HTML reports
├── tests/                               # Full test suite
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

## Features

- **Fast Scraping** – Firsttracts.com listings are parsed directly with BeautifulSoup (no AI per page)
- **Automatic Pagination** – Follows "Next" links to fetch all pages
- **AI Enrichment** – View classification (mountain/ski_area/other) and summaries via Gemini
- **Smart Filtering** – Price, bedrooms, property name, location keywords, and view type
- **Daily Reports** – HTML email with market metrics, property cards, and price change indicators
- **Local Reports** – HTML files saved to `reports/` for browser viewing
- **Change Detection** – Tracks new listings, price changes, and removed listings
- **Resilient** – Retry logic and circuit breaker for external API calls

## Email Report Features

- **Market Overview** – Total listings, average/median prices, counts of new/changed/removed
- **Property Cards** – Images, prices, bedrooms, bathrooms, sqft, location, view
- **New Badges** – Green "NEW" badge for first-time listings
- **Price Change Indicators** – Up/down arrows with dollar difference
- **Removed Listings** – Greyed-out, strikethrough styling
- **Responsive Design** – Works on mobile and desktop email clients

## Testing

Run the full test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

## Cost Estimate

- **AI Enrichment** – ~$0.005 per run (view classification for ~5 matching properties)
- **Email** – SendGrid free tier includes 100 emails/day

## License

MIT
