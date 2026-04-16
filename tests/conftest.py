"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Point at an isolated in-memory / tmp DB before importing settings-consumers.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SMTP_USER", "test@example.com")
os.environ.setdefault("EMAIL_FROM", "test@example.com")
os.environ.setdefault("EMAIL_TO", "test@example.com")


@pytest.fixture()
def settings():
    from bgscraper.config import Settings

    return Settings(
        database_url="sqlite:///:memory:",
        price_cap_apartment_eur=350_000,
        price_cap_house_eur=550_000,
        fuzzy_threshold=80,
    )


@pytest.fixture()
def db_session(settings):
    """In-memory SQLite session with all tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from bgscraper.db.base import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
