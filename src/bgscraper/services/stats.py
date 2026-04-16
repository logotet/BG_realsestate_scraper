"""Query helpers for email digests and CLI reporting."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Listing


def daily_new_listings(session: Session) -> list[Listing]:
    """Active listings that haven't been included in a daily email yet."""
    return (
        session.query(Listing)
        .filter(Listing.is_active.is_(True), Listing.notified_daily.is_(False))
        .order_by(Listing.price_eur)
        .all()
    )


def all_active_listings(session: Session) -> list[Listing]:
    """All currently active listings, for the weekly digest."""
    return (
        session.query(Listing)
        .filter(Listing.is_active.is_(True))
        .order_by(Listing.neighborhood, Listing.price_eur)
        .all()
    )


def mark_daily_notified(session: Session, listing_ids: list[int]) -> None:
    """Flag listings so they won't appear in the next daily digest."""
    if not listing_ids:
        return
    session.query(Listing).filter(Listing.id.in_(listing_ids)).update(
        {"notified_daily": True}, synchronize_session="fetch"
    )
