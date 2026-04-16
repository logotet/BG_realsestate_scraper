"""Typer CLI for the Bulgarian real-estate scraper."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import typer

app = typer.Typer(help="bgscraper — Bulgarian real estate scraper CLI.")


def _ensure_db() -> None:
    """Create tables if they don't exist (idempotent)."""
    from .db.base import Base, engine

    Base.metadata.create_all(engine)


@app.command()
def run_once(
    source: str = typer.Option("all", help="Scraper source name, or 'all'."),
) -> None:
    """Run scrapers once, store results, and expire stale listings."""
    from .config import get_settings
    from .logging_setup import configure_logging
    from .services.expiration import expire_stale
    from .services.scrape_runner import run_all, run_source

    configure_logging()
    settings = get_settings()
    _ensure_db()

    if source == "all":
        runs = run_all(settings)
    else:
        runs = [run_source(source, settings)]

    expired = expire_stale(settings)

    for r in runs:
        typer.echo(f"{r.source}: {r.items_new} new, {r.items_upd} updated [{r.status}]")
    typer.echo(f"Expired {expired} stale listing(s).")


@app.command("list-sources")
def list_sources() -> None:
    """Show available scraper sources."""
    from .scrapers.registry import all_sources

    for s in all_sources():
        typer.echo(s)


@app.command()
def stats() -> None:
    """Print active listing statistics."""
    from .db.base import session_scope
    from .db.models import Listing

    _ensure_db()
    with session_scope() as session:
        active = session.query(Listing).filter(Listing.is_active.is_(True)).count()
        new = (
            session.query(Listing)
            .filter(Listing.is_active.is_(True), Listing.notified_daily.is_(False))
            .count()
        )
        inactive = session.query(Listing).filter(Listing.is_active.is_(False)).count()
        total = session.query(Listing).count()

    typer.echo(f"Total:    {total}")
    typer.echo(f"Active:   {active}")
    typer.echo(f"New:      {new}")
    typer.echo(f"Inactive: {inactive}")


@app.command("export-csv")
def export_csv(
    output: Path = typer.Option(Path("listings.csv"), help="Output CSV file path."),
) -> None:
    """Export active listings to CSV."""
    from .db.base import session_scope
    from .services.stats import all_active_listings

    _ensure_db()
    with session_scope() as session:
        listings = all_active_listings(session)
        if not listings:
            typer.echo("No active listings to export.")
            return

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "source", "source_id", "url", "title", "price_eur",
                "property_type", "neighborhood", "area_sqm", "furnishing",
                "agency", "first_seen", "last_seen",
            ])
            for li in listings:
                writer.writerow([
                    li.source, li.source_id, li.url, li.title, li.price_eur,
                    li.property_type, li.neighborhood, li.area_sqm, li.furnishing,
                    li.agency, li.first_seen, li.last_seen,
                ])

    typer.echo(f"Exported {len(listings)} listing(s) to {output}")


@app.command("send-daily")
def send_daily() -> None:
    """Send the daily digest email with un-notified listings."""
    from .config import get_settings
    from .db.base import session_scope
    from .email.sender import send_daily_digest
    from .logging_setup import configure_logging
    from .services.stats import daily_new_listings, mark_daily_notified

    configure_logging()
    settings = get_settings()
    _ensure_db()

    with session_scope() as session:
        listings = daily_new_listings(session)
        if not listings:
            typer.echo("No new listings to send.")
            return
        send_daily_digest(settings, listings)
        mark_daily_notified(session, [li.id for li in listings])

    typer.echo(f"Sent daily digest with {len(listings)} listing(s).")


@app.command("send-weekly")
def send_weekly() -> None:
    """Send the weekly digest email with all active listings."""
    from .config import get_settings
    from .db.base import session_scope
    from .email.sender import send_weekly_digest
    from .logging_setup import configure_logging
    from .services.stats import all_active_listings

    configure_logging()
    settings = get_settings()
    _ensure_db()

    with session_scope() as session:
        listings = all_active_listings(session)
        if not listings:
            typer.echo("No active listings to send.")
            return
        send_weekly_digest(settings, listings)

    typer.echo(f"Sent weekly digest with {len(listings)} listing(s).")


@app.command("run-scheduler")
def run_scheduler() -> None:
    """Start the APScheduler loop (daily scrape + weekly digest)."""
    from .scheduler.main import start

    start()
