"""Orchestrates scraping: run scraper -> normalize -> upsert -> record run."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import Settings
from ..db.base import session_scope
from ..db.models import Listing, ScrapeRun
from ..logging_setup import get_logger
from ..normalize.pipeline import NormalizedListing, normalize
from ..scrapers import registry
from ..scrapers.http import HttpClient

log = get_logger(__name__)


def upsert_listing(session: Session, nl: NormalizedListing, now: datetime) -> str:
    """Insert or update a listing. Returns ``'new'`` or ``'updated'``."""
    existing = (
        session.query(Listing)
        .filter_by(source=nl.source, source_id=nl.source_id)
        .first()
    )
    if existing is None:
        listing = Listing(
            source=nl.source,
            source_id=nl.source_id,
            url=nl.url,
            title=nl.title,
            price_eur=nl.price_eur,
            price_raw=nl.price_raw,
            currency_raw=nl.currency_raw,
            property_type=nl.property_type.value,
            neighborhood=nl.neighborhood,
            neighborhood_raw=nl.neighborhood_raw,
            area_sqm=nl.area_sqm,
            furnishing=nl.furnishing.value,
            description=nl.description,
            images=nl.images_json,
            agency=nl.agency,
            posted_at=nl.posted_at,
            first_seen=now,
            last_seen=now,
            is_active=True,
            notified_daily=False,
        )
        session.add(listing)
        session.flush()
        return "new"

    # Update mutable fields, bump last_seen, reactivate if inactive.
    existing.title = nl.title
    existing.price_eur = nl.price_eur
    existing.price_raw = nl.price_raw
    existing.currency_raw = nl.currency_raw
    existing.neighborhood = nl.neighborhood
    existing.neighborhood_raw = nl.neighborhood_raw
    existing.area_sqm = nl.area_sqm
    existing.furnishing = nl.furnishing.value
    existing.description = nl.description
    existing.images = nl.images_json
    existing.agency = nl.agency
    existing.last_seen = now
    existing.is_active = True
    return "updated"


def run_source(source: str, settings: Settings) -> ScrapeRun:
    """Run a single scraper, normalize, upsert, and record a ScrapeRun."""
    started_at = datetime.utcnow()
    log.info("runner.start", source=source)

    scraper_cls = registry.get(source)
    with HttpClient(settings) as http:
        scraper = scraper_cls(http, settings)
        raw_listings = scraper.run()

    now = datetime.utcnow()
    items_seen = len(raw_listings)
    items_new = items_upd = 0

    with session_scope() as session:
        for raw in raw_listings:
            nl = normalize(raw, settings)
            if nl is None:
                continue
            result = upsert_listing(session, nl, now)
            if result == "new":
                items_new += 1
            else:
                items_upd += 1

        run = ScrapeRun(
            source=source,
            started_at=started_at,
            finished_at=datetime.utcnow(),
            status="ok",
            items_seen=items_seen,
            items_new=items_new,
            items_upd=items_upd,
        )
        session.add(run)

    log.info(
        "runner.done",
        source=source,
        seen=items_seen,
        new=items_new,
        updated=items_upd,
    )
    return run


def run_all(settings: Settings) -> list[ScrapeRun]:
    """Run every registered scraper concurrently, collecting run records."""
    results: list[ScrapeRun] = []
    sources = registry.all_sources()
    with ThreadPoolExecutor(max_workers=settings.source_workers) as pool:
        fs = {pool.submit(run_source, src, settings): src for src in sources}
        for future in as_completed(fs):
            src = fs[future]
            try:
                results.append(future.result())
            except Exception as exc:
                log.error("runner.source_failed", source=src, error=str(exc))
                run = ScrapeRun(
                    source=src,
                    started_at=datetime.utcnow(),
                    finished_at=datetime.utcnow(),
                    status="error",
                    items_seen=0,
                    items_new=0,
                    items_upd=0,
                    error=str(exc)[:2000],
                )
                with session_scope() as session:
                    session.add(run)
                results.append(run)
    return results
