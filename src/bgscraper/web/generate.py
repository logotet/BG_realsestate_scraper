"""Generate a static HTML dashboard from the listings database."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader

from ..config import Settings, get_settings
from ..db.base import session_scope
from ..logging_setup import get_logger
from ..services.stats import all_active_listings

log = get_logger(__name__)

_env = Environment(
    loader=PackageLoader("bgscraper", "web/templates"),
    autoescape=True,
)


def _compute_stats(listings: list) -> dict:
    """Build summary statistics for the template."""
    total = len(listings)
    if total == 0:
        return {
            "total": 0,
            "apartments": 0,
            "houses": 0,
            "sources": 0,
            "avg_price": 0,
            "min_price": 0,
            "max_price": 0,
            "by_hood": {},
            "neighborhoods": [],
        }

    prices = [li.price_eur for li in listings if li.price_eur]
    apartments = sum(1 for li in listings if li.property_type == "apartment_3room")
    houses = sum(1 for li in listings if li.property_type == "house")
    sources = sorted({li.source for li in listings})

    by_hood: dict[str, dict] = {}
    for li in listings:
        hood = li.neighborhood or "Неизвестен"
        entry = by_hood.setdefault(hood, {"count": 0, "prices": []})
        entry["count"] += 1
        if li.price_eur:
            entry["prices"].append(li.price_eur)

    for entry in by_hood.values():
        p = entry["prices"]
        entry["avg_price"] = int(sum(p) / len(p)) if p else 0

    return {
        "total": total,
        "apartments": apartments,
        "houses": houses,
        "sources": len(sources),
        "source_names": sources,
        "avg_price": int(sum(prices) / len(prices)) if prices else 0,
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "by_hood": dict(sorted(by_hood.items())),
        "neighborhoods": sorted(by_hood.keys()),
    }


def generate_site(
    output: Path | str | None = None,
    settings: Settings | None = None,
) -> Path:
    """Read active listings from DB and write a static HTML dashboard.

    Returns the path to the generated file.
    """
    settings = settings or get_settings()
    output = Path(output) if output else settings.project_root / "site" / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)

    with session_scope() as session:
        listings = all_active_listings(session)

    stats = _compute_stats(listings)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    template = _env.get_template("dashboard.j2")
    html = template.render(
        listings=listings,
        stats=stats,
        generated_at=now,
    )

    output.write_text(html, encoding="utf-8")
    log.info("web.generated", path=str(output), listings=stats["total"])
    return output
