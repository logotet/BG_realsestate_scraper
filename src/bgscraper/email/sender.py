"""SMTP email sender with Jinja2 template rendering."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, PackageLoader

from ..config import Settings
from ..constants import DealType
from ..logging_setup import get_logger

log = get_logger(__name__)

_env = Environment(
    loader=PackageLoader("bgscraper", "email/templates"),
    autoescape=True,
)


def render_daily(listings: list) -> str:
    """Render the daily digest HTML."""
    template = _env.get_template("daily.j2")
    return template.render(listings=listings, count=len(listings))


def render_weekly(listings: list) -> str:
    """Render the weekly digest HTML."""
    template = _env.get_template("weekly.j2")
    # Build summary stats.
    by_hood: dict[str, list] = {}
    for li in listings:
        hood = li.neighborhood or "Неизвестен"
        by_hood.setdefault(hood, []).append(li)
    return template.render(listings=listings, count=len(listings), by_hood=by_hood)


def send_html(settings: Settings, subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP_SSL."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as srv:
        srv.login(settings.smtp_user, settings.smtp_password)
        srv.send_message(msg)
    log.info("email.sent", subject=subject, to=settings.email_to)


def _subject_prefix(deal_type: DealType) -> str:
    return "[BGScraper Наеми]" if deal_type == DealType.RENT else "[BGScraper]"


def send_daily_digest(
    settings: Settings, listings: list, deal_type: DealType = DealType.SALE
) -> None:
    """Send the daily digest of new listings."""
    if not listings:
        log.info("email.daily.no_new_listings")
        return
    html = render_daily(listings)
    send_html(settings, f"{_subject_prefix(deal_type)} {len(listings)} нови обяви", html)


def send_weekly_digest(
    settings: Settings, listings: list, deal_type: DealType = DealType.SALE
) -> None:
    """Send the weekly digest of all active listings."""
    html = render_weekly(listings)
    send_html(
        settings,
        f"{_subject_prefix(deal_type)} Седмичен обзор: {len(listings)} активни обяви",
        html,
    )
