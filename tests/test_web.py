"""Tests for the static HTML dashboard generator."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bgscraper.db.models import Listing
from bgscraper.web.generate import _compute_stats, generate_site


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_listing(session, **overrides) -> Listing:
    defaults = {
        "source": "imot.bg",
        "source_id": "test-001",
        "url": "https://imot.bg/obiava-test-001",
        "title": "Тристаен апартамент Лозенец",
        "price_eur": 180_000,
        "property_type": "apartment_3room",
        "neighborhood": "Лозенец",
        "area_sqm": 95.0,
        "furnishing": "обзаведен",
        "agency": "Test Agency",
        "first_seen": _now(),
        "last_seen": _now(),
        "is_active": True,
        "notified_daily": False,
    }
    defaults.update(overrides)
    if "source_id" in overrides and "url" not in overrides:
        defaults["url"] = f"https://imot.bg/obiava-{defaults['source_id']}"
    li = Listing(**defaults)
    session.add(li)
    session.flush()
    return li


class TestComputeStats:
    def test_empty(self):
        stats = _compute_stats([])
        assert stats["total"] == 0
        assert stats["avg_price"] == 0
        assert stats["by_hood"] == {}

    def test_counts_and_avg(self, db_session):
        li1 = _make_listing(db_session, source_id="a1", price_eur=100_000)
        li2 = _make_listing(
            db_session,
            source_id="a2",
            price_eur=200_000,
            property_type="house",
            neighborhood="Бояна",
        )
        stats = _compute_stats([li1, li2])
        assert stats["total"] == 2
        assert stats["apartments"] == 1
        assert stats["houses"] == 1
        assert stats["avg_price"] == 150_000
        assert stats["min_price"] == 100_000
        assert stats["max_price"] == 200_000
        assert len(stats["by_hood"]) == 2

    def test_no_price(self, db_session):
        li = _make_listing(db_session, source_id="np", price_eur=None)
        stats = _compute_stats([li])
        assert stats["total"] == 1
        assert stats["avg_price"] == 0


class TestGenerateSite:
    def test_generates_html_file(self, db_session, settings, tmp_path, monkeypatch):
        _make_listing(db_session, source_id="g1", price_eur=150_000)
        _make_listing(
            db_session,
            source_id="g2",
            price_eur=250_000,
            property_type="house",
            neighborhood="Витоша",
            source="homes.bg",
        )
        db_session.commit()

        # Patch session_scope to use our test session.
        from contextlib import contextmanager

        @contextmanager
        def _mock_scope():
            yield db_session

        monkeypatch.setattr("bgscraper.web.generate.session_scope", _mock_scope)

        out = tmp_path / "dashboard.html"
        result = generate_site(output=out, settings=settings)

        assert result == out
        assert out.exists()
        html = out.read_text(encoding="utf-8")

        # Stats present.
        assert "2" in html  # total
        assert "150,000" in html or "200,000" in html  # avg price
        # Table rows present.
        assert "Лозенец" in html
        assert "Витоша" in html
        # Filters present.
        assert 'id="f-hood"' in html
        assert 'id="f-type"' in html
        # JS present.
        assert "applyFilters" in html

    def test_empty_db(self, db_session, settings, tmp_path, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def _mock_scope():
            yield db_session

        monkeypatch.setattr("bgscraper.web.generate.session_scope", _mock_scope)

        out = tmp_path / "empty.html"
        result = generate_site(output=out, settings=settings)

        assert result == out
        html = out.read_text(encoding="utf-8")
        assert "Няма активни обяви" in html
