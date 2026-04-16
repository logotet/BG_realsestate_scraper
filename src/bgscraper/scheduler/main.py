"""APScheduler blocking loop with daily scrape + weekly digest jobs."""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings
from ..db.base import Base, engine, session_scope
from ..email.sender import send_daily_digest, send_weekly_digest
from ..logging_setup import configure_logging, get_logger
from ..services.expiration import expire_stale
from ..services.scrape_runner import run_all
from ..services.stats import all_active_listings, daily_new_listings, mark_daily_notified

log = get_logger(__name__)


def _daily_job() -> None:
    settings = get_settings()
    log.info("scheduler.daily.start")

    runs = run_all(settings)
    expired = expire_stale(settings)

    with session_scope() as session:
        new = daily_new_listings(session)
        if new:
            send_daily_digest(settings, new)
            mark_daily_notified(session, [li.id for li in new])
            log.info("scheduler.daily.email_sent", count=len(new))

    log.info(
        "scheduler.daily.done",
        sources=len(runs),
        expired=expired,
    )


def _weekly_job() -> None:
    settings = get_settings()
    log.info("scheduler.weekly.start")

    with session_scope() as session:
        active = all_active_listings(session)
        if active:
            send_weekly_digest(settings, active)
            log.info("scheduler.weekly.email_sent", count=len(active))
        else:
            log.info("scheduler.weekly.no_active_listings")

    log.info("scheduler.weekly.done")


def start() -> None:
    """Configure and start the blocking scheduler."""
    configure_logging()
    settings = get_settings()

    # Ensure tables exist.
    Base.metadata.create_all(engine)

    scheduler = BlockingScheduler(timezone=settings.tz)

    scheduler.add_job(
        _daily_job,
        CronTrigger(
            hour=settings.daily_hour,
            minute=settings.daily_minute,
            timezone=settings.tz,
        ),
        id="daily_scrape",
        replace_existing=True,
    )

    scheduler.add_job(
        _weekly_job,
        CronTrigger(
            day_of_week=settings.weekly_day,
            hour=settings.weekly_hour,
            minute=settings.weekly_minute,
            timezone=settings.tz,
        ),
        id="weekly_digest",
        replace_existing=True,
    )

    log.info(
        "scheduler.starting",
        daily=f"{settings.daily_hour}:{settings.daily_minute:02d}",
        weekly=f"{settings.weekly_day} {settings.weekly_hour}:{settings.weekly_minute:02d}",
        tz=settings.tz,
    )
    scheduler.start()
