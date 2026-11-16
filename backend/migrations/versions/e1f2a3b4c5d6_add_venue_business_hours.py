"""add venue business hours and closures

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-14 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Expediente semanal e fechamentos excepcionais do estabelecimento."""
    op.create_table(
        "venue_business_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_venue_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_valid"),
        sa.CheckConstraint("opens_at < closes_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["organization_venue_id"],
            ["organization_venues.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_venue_id",
            "weekday",
            "opens_at",
            name="uq_venue_business_hours_venue_weekday_open",
        ),
    )
    op.create_index(
        "ix_venue_business_hours_venue_weekday",
        "venue_business_hours",
        ["organization_venue_id", "weekday"],
    )

    op.create_table(
        "venue_closures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_venue_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["organization_venue_id"],
            ["organization_venues.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_venue_closures_venue_start",
        "venue_closures",
        ["organization_venue_id", "starts_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_venue_closures_venue_start", table_name="venue_closures")
    op.drop_table("venue_closures")
    op.drop_index(
        "ix_venue_business_hours_venue_weekday",
        table_name="venue_business_hours",
    )
    op.drop_table("venue_business_hours")
