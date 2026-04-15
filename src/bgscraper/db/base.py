"""SQLAlchemy engine, session factory, and Base class."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Ensure data/ exists for sqlite file paths.
        if ":///" in url:
            path_part = url.split(":///", 1)[1]
            if path_part and not path_part.startswith(":"):
                from pathlib import Path

                p = Path(path_part)
                if not p.is_absolute():
                    p = settings.project_root / p
                p.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
