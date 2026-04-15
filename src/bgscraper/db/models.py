"""SQLAlchemy 2.0 models: Listing and ScrapeRun."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listings_source_sourceid"),
        UniqueConstraint("url", name="uq_listings_url"),
        Index("ix_listings_active_type", "is_active", "property_type"),
        Index("ix_listings_neighborhood", "neighborhood"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)

    title: Mapped[str | None] = mapped_column(String(512))
    price_eur: Mapped[int | None] = mapped_column(Integer)
    price_raw: Mapped[str | None] = mapped_column(String(64))
    currency_raw: Mapped[str | None] = mapped_column(String(16))
    property_type: Mapped[str] = mapped_column(String(32), nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(String(128))
    neighborhood_raw: Mapped[str | None] = mapped_column(String(256))
    area_sqm: Mapped[float | None] = mapped_column(Float)
    furnishing: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    images: Mapped[str | None] = mapped_column(Text)  # json array
    agency: Mapped[str | None] = mapped_column(String(256))
    posted_at: Mapped[date | None] = mapped_column(Date)

    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notified_daily: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Listing id={self.id} source={self.source} price_eur={self.price_eur}>"


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_upd: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScrapeRun id={self.id} source={self.source} status={self.status}>"
