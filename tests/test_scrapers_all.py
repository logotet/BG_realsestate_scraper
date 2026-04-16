"""Smoke tests for all scraper implementations — registration and URL generation."""
from __future__ import annotations

import pytest

from bgscraper.constants import PropertyType
from bgscraper.scrapers.base import SearchConfig
from bgscraper.scrapers.registry import SCRAPERS, all_sources, load_all


@pytest.fixture(autouse=True, scope="module")
def _load():
    load_all()


EXPECTED_SOURCES = [
    "adres.bg",
    "bulgarianproperties.com",
    "homes.bg",
    "imot.bg",
    "imoteka.bg",
    "imoti.net",
    "olx.bg",
    "yavlena.com",
]


def test_all_sources_registered():
    sources = all_sources()
    for expected in EXPECTED_SOURCES:
        assert expected in sources, f"{expected} not registered"


@pytest.mark.parametrize("source", EXPECTED_SOURCES)
def test_scraper_has_correct_source(source):
    cls = SCRAPERS[source]
    assert cls.source == source


@pytest.mark.parametrize("source", EXPECTED_SOURCES)
def test_iter_list_pages_yields_urls(source, settings):
    cls = SCRAPERS[source]
    scraper = cls.__new__(cls)
    scraper.settings = settings
    scraper.settings.max_list_pages = 2
    configs = scraper._build_search_configs()
    assert len(configs) >= 1

    for cfg in configs:
        pages = list(scraper.iter_list_pages(cfg))
        assert len(pages) == 2, f"{source}: expected 2 pages, got {len(pages)}"
        for url in pages:
            assert url.startswith("http"), f"{source}: URL doesn't start with http: {url}"


@pytest.mark.parametrize("source", EXPECTED_SOURCES)
def test_parse_list_page_empty_html(source, settings):
    cls = SCRAPERS[source]
    scraper = cls.__new__(cls)
    scraper.settings = settings
    cfg = SearchConfig(PropertyType.APARTMENT_3ROOM, 350_000, extra={"slug": "tristaen"})
    # Empty HTML should return empty list, not crash.
    urls = scraper.parse_list_page("<html><body></body></html>", "https://example.com")
    assert urls == []


@pytest.mark.parametrize("source", EXPECTED_SOURCES)
def test_build_search_configs_has_both_types(source, settings):
    cls = SCRAPERS[source]
    scraper = cls.__new__(cls)
    scraper.settings = settings
    configs = scraper._build_search_configs()
    types = {c.property_type for c in configs}
    assert PropertyType.APARTMENT_3ROOM in types
    assert PropertyType.HOUSE in types
