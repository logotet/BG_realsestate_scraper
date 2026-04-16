"""Scraper registry: maps source name -> scraper class."""
from __future__ import annotations

from .base import BaseScraper

# Populated by importing each concrete scraper below.
SCRAPERS: dict[str, type[BaseScraper]] = {}


def register(cls: type[BaseScraper]) -> type[BaseScraper]:
    SCRAPERS[cls.source] = cls
    return cls


def load_all() -> None:
    """Import every concrete scraper so the decorator runs."""
    # Local imports to avoid circular references at module load.
    from . import imot_bg  # noqa: F401

    # Additional scrapers will be added here as they are implemented.
    try:
        from . import imoti_net  # noqa: F401
    except ImportError:
        pass
    try:
        from . import homes_bg  # noqa: F401
    except ImportError:
        pass
    try:
        from . import olx_bg  # noqa: F401
    except ImportError:
        pass
    # adres.bg disabled — domain adfresco.adres.bg unreachable since 2026-04.
    # try:
    #     from . import adres_bg  # noqa: F401
    # except ImportError:
    #     pass
    try:
        from . import yavlena  # noqa: F401
    except ImportError:
        pass
    try:
        from . import imoteka  # noqa: F401
    except ImportError:
        pass
    try:
        from . import bulgarian_properties  # noqa: F401
    except ImportError:
        pass


def get(source: str) -> type[BaseScraper]:
    load_all()
    if source not in SCRAPERS:
        raise KeyError(f"unknown scraper: {source!r}. Known: {sorted(SCRAPERS)}")
    return SCRAPERS[source]


def all_sources() -> list[str]:
    load_all()
    return sorted(SCRAPERS)
