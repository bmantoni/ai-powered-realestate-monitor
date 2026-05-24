# Snowshoe Ski Condo Research Bot

A Python bot that scrapes real-estate listings for ski condos at Snowshoe, WV, filters them by your criteria, and sends a daily HTML email report with new listings, price changes, and market metrics.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Fetcher    │───▶│  AI Scraper  │───▶│   Storage    │
│  (httpx)     │    │ (Gemini)     │    │  (JSON File) │
└──────────────┘    └──────────────┘    └──────────────┘
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
- **AI Scraping** – Instead of brittle CSS selectors, raw HTML is fed to Gemini to extract structured listings. Adding a new source is as simple as adding a URL.
- **JSON Persistence** – A single JSON file stores all state, making it trivial to persist across GitHub Actions runs via artifacts.
- **Local Testing** – Full local execution with live data; emails can be suppressed via `DRY_RUN=true`.

## Tech Stack

- **Python 3.11+**
- **HTTP** – `httpx`
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

Create a `.env` file (see `.env.example`):

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
```

### 3. Run locally

```bash
# Test run with live data but no email
DRY_RUN=true python src/main.py

# Fast test without AI
SKIP_AI=true DRY_RUN=true python src/main.py

# Full run with email
python src/main.py
```

## Configuration

All settings are controlled via environment variables (or `.env`):

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `EMAIL_RECIPIENT` | **Yes** | Where to send reports | — |
| `GEMINI_API_KEY` | Yes* | Gemini API key | — |
| `SENDGRID_API_KEY` | Yes* | SendGrid API key | — |
| `SOURCES` | No | Comma-separated URLs | `firsttracts.com` |
| `ALLOWED_PROPERTIES` | No | Allowed property names | `Allegheny Springs,Rimfire Lodge` |
| `MIN_PRICE` | No | Minimum price filter | `150000` |
| `MAX_PRICE` | No | Maximum price filter | `200000` |
| `DRY_RUN` | No | Skip email sending | `false` |
| `SKIP_AI` | No | Skip AI enrichment | `false` |
| `DATA_PATH` | No | State file path | `./data/properties.json` |

\*At least one AI provider is required unless `SKIP_AI=true`.

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
│   ├── ai_scraper.py                    # AI-powered extraction
│   ├── ai_enrichment.py                 # View classification
│   ├── storage.py                       # JSON persistence
│   ├── filter.py                        # Criteria matching
│   ├── email_generator.py               # Jinja2 HTML rendering
│   └── email_sender.py                  # SendGrid delivery
├── templates/
│   └── email.html                       # Email template
├── data/
│   └── .gitkeep                         # State files
├── tests/                               # Full test suite
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

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

- **AI Scraping** – ~$0.02 per run with Gemini Flash (well within free tier)
- **Email** – SendGrid free tier includes 100 emails/day

## License

MIT
