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
