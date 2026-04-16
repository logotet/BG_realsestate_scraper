"""Tests for email template rendering and sender wiring."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bgscraper.email.sender import render_daily, render_weekly, send_html


def _fake_listing(**overrides):
    defaults = dict(
        url="https://imot.bg/obiava-1",
        title="Тристаен в Лозенец",
        neighborhood="Лозенец",
        price_eur=200_000,
        area_sqm=90.0,
        source="imot.bg",
        property_type="apartment_3room",
        furnishing="furnished",
        agency="TestAgency",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# -- Template rendering -----------------------------------------------------


class TestDailyTemplate:
    def test_renders_listings(self):
        listings = [_fake_listing(), _fake_listing(title="Къща в Бояна", price_eur=400_000)]
        html = render_daily(listings)
        assert "2 нови обяви" in html
        assert "Лозенец" in html
        assert "200,000" in html
        assert "Къща в Бояна" in html
        assert "400,000" in html

    def test_empty_listings(self):
        html = render_daily([])
        assert "0 нови обяви" in html


class TestWeeklyTemplate:
    def test_renders_summary_and_listings(self):
        listings = [
            _fake_listing(neighborhood="Лозенец"),
            _fake_listing(neighborhood="Лозенец", price_eur=250_000),
            _fake_listing(neighborhood="Бояна", price_eur=300_000),
        ]
        html = render_weekly(listings)
        assert "3 активни обяви" in html
        assert "Лозенец" in html
        assert "Бояна" in html
        # Summary table should exist.
        assert "Средна цена" in html or "По квартали" in html


# -- send_html --------------------------------------------------------------


class TestSendHtml:
    @patch("bgscraper.email.sender.smtplib.SMTP_SSL")
    def test_sends_via_smtp(self, mock_smtp_cls, settings):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_html(settings, "Test Subject", "<h1>Hello</h1>")

        mock_smtp_cls.assert_called_once_with(settings.smtp_host, settings.smtp_port)
        mock_server.login.assert_called_once_with(settings.smtp_user, settings.smtp_password)
        mock_server.send_message.assert_called_once()
