# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`bgscraper` scrapes the largest Bulgarian real-estate portals daily, filters listings
to a fixed set of Sofia neighborhoods and price caps, deduplicates and tracks
expirations in SQLite, emails a daily digest of new matches plus a weekly digest of all
active listings, and regenerates a static HTML dashboard. It runs unattended via
APScheduler (local) or a GitHub Actions cron (`.github/workflows/daily_scrape.yml`).

There are two search profiles, selected by a `DealType` enum threaded through the whole
pipeline (`--deal-type` on the CLI, default `sale`):

- **sale** — 3-room apartments and houses, €150k–550k.
- **rent** — 2-room apartments, €450–700/month, drops ads that explicitly refuse pets
  (`normalize/pets.py`; no mention of pets = kept). Rent listings live in a **separate
  SQLite DB** (`rent_database_url`, default `data/rent_listings.db`) so all queries,
  digests, and the `notified_daily` flag stay per-profile with no schema changes. The
  CLI points `DATABASE_URL` at the rent DB when `--deal-type rent` is passed and the
  env var isn't already set. Scrapers opt into rent via a `supports` class attribute —
  currently only `imot.bg` (`prodazhbi`→`naemi` URL segment, slug `dvustaen`). The rent
  cron is `.github/workflows/rent_scrape.yml`; the local APScheduler and the HTML
  dashboard remain sale-only.

The repository root is the `BG_realsestate_scraper/` directory (the package is `bgscraper`,
under `src/`).

## Commands

```bash
# Setup (Windows bash)
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env          # then set SMTP_PASSWORD etc.
alembic upgrade head          # or rely on _ensure_db() which create_all()s tables

# Tests
pytest                        # config in pyproject.toml (-q, testpaths=tests)
pytest tests/test_normalize.py
pytest tests/test_normalize.py::test_name -q
pytest --cov=bgscraper        # pytest-cov is installed

# Lint / type-check
ruff check src tests          # rules: E,F,I,B,UP,SIM; line-length 100
ruff format src tests
mypy src

# CLI (entrypoint `bgscraper` = bgscraper.cli:app)
bgscraper list-sources
bgscraper run-once --source imot.bg   # default --source all
bgscraper run-once --deal-type rent   # rent profile; writes data/rent_listings.db
bgscraper send-daily                  # also accepts --deal-type rent
bgscraper send-weekly
bgscraper generate-site
bgscraper stats
bgscraper export-csv --output listings.csv
bgscraper run-scheduler               # blocking APScheduler loop
```

`daily_scrape.bat` chains `run-once → send-daily → generate-site` for Windows Task
Scheduler. Note its hard-coded path (`C:\Users\Vladimir Vasilev\projects\bg-realestate-scraper`)
differs from the actual checkout location.

## Architecture

The pipeline is **scrape → normalize → upsert → notify**, orchestrated by
`services/scrape_runner.py`:

1. **Scrapers** (`scrapers/`) produce `RawListing` dataclasses (untransformed strings).
   Each subclass of `BaseScraper` implements `iter_list_pages`, `parse_list_page`, and
   `parse_detail`. `BaseScraper.run()` drives pagination, fetches detail pages
   concurrently (`ThreadPoolExecutor`, `detail_workers`), and has two safety valves:
   stop after 3 consecutive list-page failures, and a circuit breaker that aborts a
   source once >50% of detail fetches fail (after ≥10 attempts).
2. **Normalize** (`normalize/pipeline.py`) converts `RawListing → NormalizedListing`,
   **returning `None` to drop a listing**. This is the single filtering choke point:
   property-type classification, currency→EUR conversion, price min/cap, neighborhood
   canonicalization, and a series of business rules (e.g. в.з. zones allow houses only,
   apartments must be ≥80 m², drops non-Sofia cities and wrong property types by title
   keyword). When adding filters, add them here, not in scrapers.
3. **Upsert** (`scrape_runner.upsert_listing`) dedupes on `(source, source_id)`, bumps
   `last_seen`, and reactivates previously-inactive listings. Each run writes a
   `ScrapeRun` audit row.
4. **Expiration** (`services/expiration.py`) marks listings inactive when not seen for
   `stale_days` (default 3).
5. **Notify** (`email/sender.py` + Jinja templates `email/templates/*.j2`). Daily digest
   uses `notified_daily` flag so each listing is emailed once; weekly digest sends all
   active listings.

### Scraper registry

`scrapers/registry.py` maps `source name → class` via the `@register` decorator.
`load_all()` imports each concrete scraper inside `try/except ImportError` so a
half-finished scraper never breaks the others. Only `imot.bg` is fully implemented and
unconditionally imported; the rest (`imoti_net`, `homes_bg`, `yavlena`, `imoteka`,
`bulgarian_properties`) are best-effort. Two sources are intentionally disabled:
`adres_bg` (import commented out — domain unreachable) and `olx_bg` (import removed
from `load_all()` entirely; the file still carries `@register` but never loads —
re-enable by re-adding the import). To add a source: create
`scrapers/<name>.py`, subclass `BaseScraper`, decorate with `@register`, and add an
import line to `load_all()`.

### Configuration & data

- **Settings** (`config.py`): pydantic-settings loaded from `.env` at `PROJECT_ROOT`.
  `get_settings()` is `lru_cache`d — a single instance per process. Price caps,
  fuzzy threshold, delays, worker counts, SMTP, and scheduler times all live here.
- **Neighborhoods** (`constants.py`): the fixed `NEIGHBORHOODS` list plus
  `NEIGHBORHOOD_ALIASES` define the entire search universe;
  `HOUSES_ONLY_NEIGHBORHOODS` lists non-в.з. areas where apartments are dropped.
  `normalize/neighborhood.py` canonicalizes raw strings via alias map → substring →
  rapidfuzz `WRatio` (threshold from `fuzzy_threshold`). Editing the neighborhood set
  is a deliberate product decision, not a refactor.
- **DB** (`db/base.py`, `db/models.py`): SQLAlchemy 2.0 (typed `Mapped` columns),
  SQLite by default at `data/listings.db`. `session_scope()` is the
  commit/rollback context manager. The engine sets `check_same_thread=False` because
  scraping and upserts run across threads. Schema changes go through Alembic
  (`alembic/versions/`), though `_ensure_db()` / `create_all()` will also create tables
  for fresh DBs.

### HTTP

`scrapers/http.py` `HttpClient` wraps `httpx` with HTTP/2, rotating User-Agents
(`resources/user_agents.txt`), jittered delays (`request_min/max_delay`), tenacity
retries on `{429,500,502,503,504}` + transport errors, and meta-tag charset detection
(Bulgarian sites are often windows-1251, not UTF-8). Always fetch through this client.

### Logging

`structlog` configured in `logging_setup.py`; use `get_logger(__name__)` and emit
structured events like `log.info("runner.start", source=source)` (event name + kwargs),
matching the existing dotted-event convention.

## Testing notes

- `tests/conftest.py` forces `DATABASE_URL=sqlite:///:memory:` and dummy SMTP/email env
  vars *before* importing settings consumers, and prepends `src/` to `sys.path`. Provides
  `settings` and `db_session` fixtures.
- Scraper parsing is tested against saved HTML in `tests/fixtures/imot_bg/` — add
  fixtures there rather than hitting the network in tests.
