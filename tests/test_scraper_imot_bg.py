"""Tests for the imot.bg scraper — parse methods and registry integration."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bgscraper.constants import PropertyType
from bgscraper.scrapers.base import SearchConfig
from bgscraper.scrapers.imot_bg import ImotBgScraper, _extract_source_id, _parse_date

FIXTURES = Path(__file__).parent / "fixtures" / "imot_bg"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def cfg_apartment():
    return SearchConfig(
        property_type=PropertyType.APARTMENT_3ROOM,
        price_cap_eur=350_000,
        extra={"slug": "tristaen"},
    )


@pytest.fixture()
def cfg_house():
    return SearchConfig(
        property_type=PropertyType.HOUSE,
        price_cap_eur=550_000,
        extra={"slug": "kashta"},
    )


# -- Registry integration --------------------------------------------------


def test_registry_has_imot_bg():
    from bgscraper.scrapers.registry import SCRAPERS, load_all

    load_all()
    assert "imot.bg" in SCRAPERS
    assert SCRAPERS["imot.bg"] is ImotBgScraper


# -- URL helpers ------------------------------------------------------------


def test_extract_source_id():
    url = "https://www.imot.bg/obiava-1c176754466608675-prodava-tristaen-apartament"
    assert _extract_source_id(url) == "1c176754466608675"


def test_extract_source_id_fallback():
    assert _extract_source_id("https://example.com/no-id") == "https://example.com/no-id"


# -- iter_list_pages --------------------------------------------------------


def test_iter_list_pages_apartment(settings, cfg_apartment):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings
    scraper.settings.max_list_pages = 3

    pages = list(scraper.iter_list_pages(cfg_apartment))
    assert len(pages) == 3
    assert pages[0] == "https://www.imot.bg/obiavi/prodazhbi/tristaen/grad-sofiya"
    assert pages[1] == "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya/tristaen/p-2"
    assert pages[2] == "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya/tristaen/p-3"


def test_iter_list_pages_house(settings, cfg_house):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings
    scraper.settings.max_list_pages = 2

    pages = list(scraper.iter_list_pages(cfg_house))
    assert len(pages) == 2
    assert pages[0] == "https://www.imot.bg/obiavi/prodazhbi/kashta/grad-sofiya"
    assert pages[1] == "https://www.imot.bg/obiavi/prodazhbi/grad-sofiya/kashta/p-2"


# -- parse_list_page --------------------------------------------------------


def test_parse_list_page_returns_detail_urls(settings, cfg_apartment):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings

    html = _read_fixture("list_page.html")
    urls = scraper.parse_list_page(html, "https://www.imot.bg/obiavi/prodazhbi/tristaen/grad-sofiya")

    # Should find 3 unique obiava links, not the category/agency links.
    assert len(urls) == 3
    assert all("obiava-" in u for u in urls)
    assert all(u.startswith("https://") for u in urls)
    # Verify deduplication (each URL appears exactly once despite duplicate hrefs).
    assert len(urls) == len(set(urls))


def test_parse_list_page_empty_returns_empty(settings, cfg_apartment):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings

    html = _read_fixture("empty_list_page.html")
    urls = scraper.parse_list_page(html, "https://www.imot.bg/obiavi/prodazhbi/tristaen/grad-sofiya")
    assert urls == []


# -- parse_detail -----------------------------------------------------------


def test_parse_detail_extracts_all_fields(settings, cfg_apartment):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings

    html = _read_fixture("detail_page.html")
    url = "https://www.imot.bg/obiava-1c176754466608675-prodava-tristaen-apartament-grad-sofiya-lozenets"
    raw = scraper.parse_detail(html, url, cfg_apartment)

    assert raw.source == "imot.bg"
    assert raw.source_id == "1c176754466608675"
    assert raw.url == url
    assert "3-стаен" in raw.title
    assert raw.price_raw is not None
    assert raw.currency_raw in ("EUR", "BGN")
    assert raw.property_type == PropertyType.APARTMENT_3ROOM
    assert raw.neighborhood_raw == "Лозенец"
    assert raw.area_sqm == 102.0
    assert raw.furnishing_raw is not None
    assert "обзаведен" in raw.furnishing_raw
    assert raw.description is not None and len(raw.description) > 50
    assert len(raw.images) == 3  # 3 listing images, logo excluded
    assert all("focus.bg" in img for img in raw.images)
    assert raw.agency == "LUXIMMO FINEST ESTATES"
    assert raw.posted_at == date(2026, 4, 15)


def test_parse_detail_property_type_from_config(settings, cfg_house):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings

    html = _read_fixture("detail_page.html")
    url = "https://www.imot.bg/obiava-1c176754466608675-prodava-kashta-grad-sofiya-boyana"
    raw = scraper.parse_detail(html, url, cfg_house)

    assert raw.property_type == PropertyType.HOUSE
    assert raw.property_type_raw == "kashta"


# -- Date parsing -----------------------------------------------------------


def test_parse_bulgarian_date():
    assert _parse_date("15 април, 2026 г.") == date(2026, 4, 15)
    assert _parse_date("3 януари 2025 г., 14:30") == date(2025, 1, 3)
    assert _parse_date("no date here") is None


# -- build_search_configs ---------------------------------------------------


def test_build_search_configs(settings):
    scraper = ImotBgScraper.__new__(ImotBgScraper)
    scraper.settings = settings
    configs = scraper._build_search_configs()

    assert len(configs) == 2
    types = {c.property_type for c in configs}
    assert types == {PropertyType.APARTMENT_3ROOM, PropertyType.HOUSE}

    apt_cfg = next(c for c in configs if c.property_type == PropertyType.APARTMENT_3ROOM)
    assert apt_cfg.price_cap_eur == 350_000
    assert apt_cfg.extra["slug"] == "tristaen"

    house_cfg = next(c for c in configs if c.property_type == PropertyType.HOUSE)
    assert house_cfg.price_cap_eur == 550_000
    assert house_cfg.extra["slug"] == "kashta"
