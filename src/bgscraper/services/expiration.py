"""Detect and mark stale listings as inactive."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..config import Settings
from ..db.base import session_scope
from ..db.models import Listing
from ..logging_setup import get_logger

log = get_logger(__name__)


def expire_stale(settings: Settings) -> int:
    """Mark listings as inactive when not seen for ``stale_days``.

    Returns the number of listings expired.
    """
    cutoff = datetime.utcnow() - timedelta(days=settings.stale_days)
    with session_scope() as session:
        count = (
            session.query(Listing)
            .filter(Listing.is_active.is_(True), Listing.last_seen < cutoff)
            .update({"is_active": False}, synchronize_session="fetch")
        )
    log.info("expiration.done", expired=count, cutoff=cutoff.isoformat())
    return count
