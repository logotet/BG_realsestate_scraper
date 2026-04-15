# bg-realestate-scraper

Daily-running scraper for the largest Bulgarian real-estate portals. Filters
listings by Sofia neighborhoods and price, stores them locally, deduplicates,
tracks expirations, and emails a daily digest of new matches plus a weekly
digest of all active listings.

> Full docs are written in the final step — see `.env.example` for config and
> `src/bgscraper/` for the package layout.

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows bash
pip install -e ".[dev]"
cp .env.example .env            # then edit SMTP_PASSWORD etc.
alembic upgrade head
bgscraper run-once --source imot.bg
```

## Layout

```
src/bgscraper/
    config.py           settings
    constants.py        neighborhoods, canonical names
    db/                 models, session, upsert
    scrapers/           base + per-site scrapers
    normalize/          currency, neighborhood, filters
    services/           scrape_runner, expiration, stats
    email/              smtp + jinja templates
    scheduler/          apscheduler entrypoint
    cli.py              typer commands
```

## Targets (v1)

imot.bg, imoti.net, homes.bg, olx.bg, adres.bg, yavlena.com, imoteka.bg,
bulgarianproperties.bg.
