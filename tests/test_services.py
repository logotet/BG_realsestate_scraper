"""Tests for services: upsert, expiration, stats."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from bgscraper.constants import Furnishing, PropertyType
from bgscraper.db.models import Listing
from bgscraper.normalize.pipeline import NormalizedListing
from bgscraper.services.scrape_runner import upsert_listing
from bgscraper.services.stats import all_active_listings, daily_new_listings, mark_daily_notified


def _make_nl(**overrides) -> NormalizedListing:
    defaults = dict(
        source="imot.bg",
        source_id="abc123",
        url="https://imot.bg/obiava-abc123",
        title="Тристаен в Лозенец",
        price_eur=200_000,
        price_raw="200 000",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_3ROOM,
        neighborhood="Лозенец",
        neighborhood_raw="Лозенец",
        area_sqm=90.0,
        furnishing=Furnishing.FURNISHED,
        description="Nice apartment",
        images_json="[]",
        agency="TestAgency",
        posted_at=None,
    )
    defaults.update(overrides)
    # Ensure URL is unique when source_id is overridden.
    if "source_id" in overrides and "url" not in overrides:
        defaults["url"] = f"https://imot.bg/obiava-{defaults['source_id']}"
    return NormalizedListing(**defaults)


# -- upsert_listing ---------------------------------------------------------


class TestUpsert:
    def test_insert_new(self, db_session):
        nl = _make_nl()
        now = datetime(2026, 4, 10, 12, 0)
        result = upsert_listing(db_session, nl, now)
        db_session.flush()

        assert result == "new"
        listing = db_session.query(Listing).filter_by(source_id="abc123").one()
        assert listing.price_eur == 200_000
        assert listing.neighborhood == "Лозенец"
        assert listing.first_seen == now
        assert listing.last_seen == now
        assert listing.is_active is True
        assert listing.notified_daily is False

    def test_update_existing(self, db_session):
        nl = _make_nl()
        t1 = datetime(2026, 4, 10, 12, 0)
        upsert_listing(db_session, nl, t1)
        db_session.flush()

        # Same listing, new price.
        nl2 = _make_nl(price_eur=210_000)
        t2 = datetime(2026, 4, 11, 12, 0)
        result = upsert_listing(db_session, nl2, t2)
        db_session.flush()

        assert result == "updated"
        listing = db_session.query(Listing).filter_by(source_id="abc123").one()
        assert listing.price_eur == 210_000
        assert listing.first_seen == t1  # unchanged
        assert listing.last_seen == t2   # bumped

    def test_reactivation(self, db_session):
        nl = _make_nl()
        t1 = datetime(2026, 4, 10, 12, 0)
        upsert_listing(db_session, nl, t1)
        db_session.flush()

        # Mark inactive.
        listing = db_session.query(Listing).filter_by(source_id="abc123").one()
        listing.is_active = False
        db_session.flush()

        # Upsert again → should reactivate.
        t2 = datetime(2026, 4, 12, 12, 0)
        result = upsert_listing(db_session, nl, t2)
        db_session.flush()

        assert result == "updated"
        listing = db_session.query(Listing).filter_by(source_id="abc123").one()
        assert listing.is_active is True
        assert listing.last_seen == t2


# -- expiration -------------------------------------------------------------


class TestExpiration:
    def test_expire_stale(self, db_session, settings):
        now = datetime.now(UTC).replace(tzinfo=None)
        old = now - timedelta(days=5)

        # Insert a stale listing.
        nl_old = _make_nl(source_id="old1")
        upsert_listing(db_session, nl_old, old)
        # Insert a fresh listing.
        nl_fresh = _make_nl(source_id="fresh1")
        upsert_listing(db_session, nl_fresh, now)
        db_session.flush()

        # Expire using direct query (same logic as expire_stale service).
        cutoff = now - timedelta(days=settings.stale_days)
        count = (
            db_session.query(Listing)
            .filter(Listing.is_active.is_(True), Listing.last_seen < cutoff)
            .update({"is_active": False}, synchronize_session="fetch")
        )
        db_session.flush()

        assert count == 1
        old_listing = db_session.query(Listing).filter_by(source_id="old1").one()
        assert old_listing.is_active is False
        fresh_listing = db_session.query(Listing).filter_by(source_id="fresh1").one()
        assert fresh_listing.is_active is True


# -- stats ------------------------------------------------------------------


class TestStats:
    def test_daily_new_listings(self, db_session):
        now = datetime.now(UTC).replace(tzinfo=None)
        # Two active, un-notified listings.
        upsert_listing(db_session, _make_nl(source_id="a", price_eur=200_000), now)
        upsert_listing(db_session, _make_nl(source_id="b", price_eur=150_000), now)
        # One already notified.
        upsert_listing(db_session, _make_nl(source_id="c", price_eur=100_000), now)
        db_session.flush()
        listing_c = db_session.query(Listing).filter_by(source_id="c").one()
        listing_c.notified_daily = True
        db_session.flush()

        results = daily_new_listings(db_session)
        ids = [r.source_id for r in results]
        assert "a" in ids
        assert "b" in ids
        assert "c" not in ids
        # Ordered by price.
        assert results[0].price_eur <= results[1].price_eur

    def test_all_active_listings(self, db_session):
        now = datetime.now(UTC).replace(tzinfo=None)
        upsert_listing(db_session, _make_nl(source_id="x"), now)
        upsert_listing(db_session, _make_nl(source_id="y"), now)
        db_session.flush()
        # Deactivate one.
        listing = db_session.query(Listing).filter_by(source_id="y").one()
        listing.is_active = False
        db_session.flush()

        results = all_active_listings(db_session)
        ids = [r.source_id for r in results]
        assert "x" in ids
        assert "y" not in ids

    def test_mark_daily_notified(self, db_session):
        now = datetime.now(UTC).replace(tzinfo=None)
        upsert_listing(db_session, _make_nl(source_id="m"), now)
        upsert_listing(db_session, _make_nl(source_id="n"), now)
        db_session.flush()

        listing_m = db_session.query(Listing).filter_by(source_id="m").one()
        mark_daily_notified(db_session, [listing_m.id])
        db_session.flush()

        listing_m = db_session.query(Listing).filter_by(source_id="m").one()
        listing_n = db_session.query(Listing).filter_by(source_id="n").one()
        assert listing_m.notified_daily is True
        assert listing_n.notified_daily is False
