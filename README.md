# EventRadar 🎯

**EventRadar** is a Python data pipeline that scrapes tech, founder, and networking events + hackathons for **Hyderabad**, **India**, and **globally** from 20+ public sources, normalizes them into one schema, deduplicates, and stores them in **MongoDB**.

No web frontend, no API server — just a clean, resilient data pipeline.

---

## ⚡ 5-Minute Setup

### 1. Create a free MongoDB Atlas cluster

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) → **Start Free**
2. Create a **Shared / M0** cluster (free tier)
3. In **Database Access**, create a user with read/write permissions
4. In **Network Access**, allow your IP (or `0.0.0.0/0` for anywhere)
5. Click **Connect** → **Drivers** → **Python** → copy the connection string

### 2. Configure your environment

```bash
cp .env.example .env
```

Edit `.env` and set your `MONGO_URI`:

```
MONGO_URI=mongodb+srv://myuser:mypassword@mycluster.mongodb.net/?retryWrites=true&w=majority
```

That's the **only** required value. Everything else is optional.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the pipeline

```bash
# Full run — all no-key sources
python main.py run

# Test a single source
python main.py run --only luma

# Skip slow sources
python main.py run --skip allevents --skip townscript

# List all available sources
python main.py sources

# View stored counts by scope/category/source
python main.py stats
```

---

## 📁 Project Structure

```
eventradar/
  __init__.py          Package root
  config.py            Loads .env; exposes all settings as typed constants
  db.py                MongoDB client, index setup, upsert + run-log helpers
  http.py              fetch() with retries/timeout/UA rotation
  schema.py            Event model, date parsing, normalization
  dedup.py             Dice-coefficient bigram similarity, dedup pipeline
  categorize.py        Keyword rules → category (tech|founder|networking) + tags
  normalize_llm.py     Optional LLM fallback normalizer
  runner.py            Parallel orchestrator, normalize→dedup→store→summarize
  sources/
    __init__.py        Source registry (name, fn, needs_key)
    luma.py            PRIMARY — discover API + __NEXT_DATA__ HTML parse
    devfolio.py        Devfolio hackathons (API + HTML fallback)
    devpost.py         Devpost hackathons (paginated API)
    unstop.py          Unstop India hackathons (API)
    hackerearth.py     HackerEarth events (API)
    mlh.py             MLH season events (HTML)
    devevents.py       dev.events India (HTML)
    knowafest.py       KnowAFest Telangana (HTML)
    reskilll.py        Reskilll all-hacks (HTML)
    hack2skill.py      Hack2Skill explore (HTML)
    lablab.py          LabLab AI hackathons (Next.js + HTML)
    commudle.py        Commudle Hyderabad (API)
    allevents.py       AllEvents.in Hyderabad tech (HTML)
    townscript.py      Townscript Hyderabad tech (HTML)
    konfhub.py         KonfHub Hyderabad (Next.js + HTML)
    gdg_hyderabad.py   GDG Hyderabad (Bevy API + HTML)
    eventbrite.py      Eventbrite [KEY-GATED: EVENTBRITE_TOKEN]
    meetup.py          Meetup GraphQL [KEY-GATED: MEETUP_TOKEN]
    luma_api.py        Luma Plus API [KEY-GATED: LUMA_API_KEY]
    corporate_seed.py  Static recurring programs (no network)
main.py               CLI entrypoint
```

---

## 🗄️ Event Schema

Every stored event has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `title` | str | Original event title |
| `normalized_title` | str | Lowercase, alphanumeric, for dedup |
| `description` | str | ≤300 chars |
| `event_type` | str | `hackathon\|meetup\|conference\|corporate_challenge\|program\|workshop` |
| `category` | str | `tech\|founder\|networking` |
| `scope` | str | `hyderabad\|india\|global` |
| `mode` | str | `online\|offline\|hybrid\|null` |
| `city` | str | `hyderabad\|bangalore\|other\|null` |
| `venue` | str | Venue/address |
| `start_date` | str | ISO `YYYY-MM-DD` |
| `end_date` | str | ISO `YYYY-MM-DD` |
| `registration_deadline` | str | ISO `YYYY-MM-DD` |
| `prize_pool` | str | e.g. `"$10,000"` |
| `organizer` | str | Organizer name |
| `registration_url` | str | **Required** — absolute URL |
| `source_name` | str | Which scraper found this |
| `source_event_id` | str | Platform ID or slug |
| `tags` | list | Lowercase technology tags |
| `is_student_friendly` | bool | Student-oriented heuristic |
| `is_free` | bool\|null | Free to enter |
| `scraped_at` | str | ISO timestamp |

**Unique index**: `(source_name, source_event_id)` — re-running is fully idempotent.

---

## 🔑 Adding Optional API Keys

Edit your `.env` file and uncomment / set the relevant variables:

```bash
# Eventbrite
EVENTBRITE_TOKEN=your_token_here

# Meetup OAuth2 bearer token
MEETUP_TOKEN=your_token_here

# Luma Plus API key
LUMA_API_KEY=your_key_here
```

Key-gated sources print `skipped: no key (VAR_NAME not set)` when absent and never block the run.

### Optional LLM normalization

Set any one of these to enable LLM-assisted normalization for "messy HTML" sources:

```bash
GEMINI_API_KEY=...      # Priority 1
OPENAI_API_KEY=...      # Priority 2
ANTHROPIC_API_KEY=...   # Priority 3
```

LLM normalization is purely additive — it only fills fields that the deterministic parser left empty, and the pipeline never depends on it.

---

## ➕ Adding a New Source

1. Create `eventradar/sources/mysource.py`:

```python
"""sources/mysource.py — My custom source."""
from eventradar.http import fetch

SOURCE_NAME = "mysource"

def scrape() -> list[dict]:
    kind, data = fetch("https://example.com/api/events", want="json")
    if kind == "error":
        return []
    results = []
    for ev in data.get("events", []):
        results.append({
            "title": ev["name"],
            "registration_url": ev["url"],
            "source_name": SOURCE_NAME,
            "source_event_id": str(ev["id"]),
            "event_type": "hackathon",
            "scope": "global",
            # ... other fields as available
        })
    return results
```

2. Register it in `eventradar/sources/__init__.py`:

```python
from eventradar.sources import mysource
# Inside _build_registry():
Source("mysource", mysource.scrape, None),  # None = no key needed
```

3. Test it:

```bash
python main.py run --only mysource
```

**Rules a scraper must follow:**
- Return `[]` and log on any error — never raise
- Set `registration_url` (required) and `source_event_id` (required)
- All other fields optional — `normalize_event()` fills defaults

---

## 🗃️ MongoDB Collections

**`event_radar.events`** — main events store
- Unique index: `(source_name, source_event_id)`
- Query indexes: `normalized_title`, `start_date`, `registration_deadline`, `scope`, `category`, `city`

**`event_radar.scrape_runs`** — one row per source per run
- Fields: `run_at`, `source_name`, `items_found`, `items_stored`, `status`, `error_message`

---

## 🔧 Defaults & Design Choices

| Setting | Default | Notes |
|---------|---------|-------|
| `MONGO_URI` | `mongodb://localhost:27017` | Local MongoDB for zero-config testing |
| `HTTP_TIMEOUT` | 15s | Per-request timeout |
| `HTTP_RETRIES` | 3 | Exponential backoff: 2s, 4s, 8s |
| `HTTP_PAGE_WAIT` | 2s | Sleep between paginated requests |
| `RUNNER_MAX_WORKERS` | 6 | ThreadPoolExecutor workers |
| `DEDUP_SIMILARITY_THRESHOLD` | 0.82 | Dice coefficient; raise to be stricter |
| `DEDUP_DATE_WINDOW_DAYS` | 3 | +/-3 days window for Mongo candidate lookup |
| `CORPORATE_SEED_WINDOW_DAYS` | 60 | Emit seed events within 60 days of window |

All can be overridden in `.env`.

---

## 🛡️ Resilience

- Every source is wrapped in `try/except` — one broken source **never** stops the run
- HTTP: 15s timeout, 3 retries with exponential backoff, realistic browser User-Agent
- 2s wait between paginated/per-page requests (respects rate limits)
- Upsert is idempotent — re-runs never create duplicates
- Dedup: Dice similarity (0.82 threshold) + date proximity + city/mode matching

---

## 📋 CLI Reference

```bash
python main.py run                         # run all sources
python main.py run --only luma             # run only luma
python main.py run --only luma --only devpost  # run luma and devpost
python main.py run --skip meetup --skip eventbrite  # skip two sources
python main.py run -v                      # verbose/debug logging
python main.py sources                     # list sources + key requirements
python main.py stats                       # MongoDB aggregate stats
```
