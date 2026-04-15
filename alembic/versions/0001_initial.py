"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-15

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("price_eur", sa.Integer(), nullable=True),
        sa.Column("price_raw", sa.String(length=64), nullable=True),
        sa.Column("currency_raw", sa.String(length=16), nullable=True),
        sa.Column("property_type", sa.String(length=32), nullable=False),
        sa.Column("neighborhood", sa.String(length=128), nullable=True),
        sa.Column("neighborhood_raw", sa.String(length=256), nullable=True),
        sa.Column("area_sqm", sa.Float(), nullable=True),
        sa.Column("furnishing", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("images", sa.Text(), nullable=True),
        sa.Column("agency", sa.String(length=256), nullable=True),
        sa.Column("posted_at", sa.Date(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "notified_daily",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_listings_source_sourceid"),
        sa.UniqueConstraint("url", name="uq_listings_url"),
    )
    op.create_index(
        "ix_listings_active_type", "listings", ["is_active", "property_type"]
    )
    op.create_index("ix_listings_neighborhood", "listings", ["neighborhood"])

    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("items_seen", sa.Integer(), server_default=sa.text("0")),
        sa.Column("items_new", sa.Integer(), server_default=sa.text("0")),
        sa.Column("items_upd", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scrape_runs")
    op.drop_index("ix_listings_neighborhood", table_name="listings")
    op.drop_index("ix_listings_active_type", table_name="listings")
    op.drop_table("listings")
