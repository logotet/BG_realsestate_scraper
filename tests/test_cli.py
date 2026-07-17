"""Tests for the CLI commands."""
from __future__ import annotations

from typer.testing import CliRunner

from bgscraper.cli import app

runner = CliRunner()


def test_list_sources():
    result = runner.invoke(app, ["list-sources"])
    assert result.exit_code == 0
    assert "imot.bg" in result.output


def test_stats_empty_db():
    """Stats should work even with an empty / fresh database."""
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "Total:" in result.output
    assert "Active:" in result.output


def test_stats_rent_flag():
    """--deal-type rent is accepted (DATABASE_URL from conftest wins, so no rent DB is created)."""
    result = runner.invoke(app, ["stats", "--deal-type", "rent"])
    assert result.exit_code == 0
    assert "Total:" in result.output


def test_run_once_rejects_unsupported_rent_source():
    """A source without rent support fails before any network access."""
    result = runner.invoke(app, ["run-once", "--deal-type", "rent", "--source", "homes.bg"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


def test_apply_deal_type_env(monkeypatch):
    import os

    from bgscraper.cli import _apply_deal_type_env
    from bgscraper.constants import DealType

    # Already set (the normal test/CI situation): left untouched.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///already-set.db")
    _apply_deal_type_env(DealType.RENT)
    assert os.environ["DATABASE_URL"] == "sqlite:///already-set.db"

    # Unset + rent: points at the rent DB.
    monkeypatch.delenv("DATABASE_URL")
    _apply_deal_type_env(DealType.RENT)
    assert "rent_listings.db" in os.environ["DATABASE_URL"]

    # Unset + sale: stays unset.
    monkeypatch.delenv("DATABASE_URL")
    _apply_deal_type_env(DealType.SALE)
    assert "DATABASE_URL" not in os.environ
