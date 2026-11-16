"""add booking pricing snapshot

Revision ID: b8e1f2a3c4d5
Revises: b7d4f1a9c620
Create Date: 2026-11-14 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e1f2a3c4d5"
down_revision: str | Sequence[str] | None = "b7d4f1a9c620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Congela faixa e ingressos por vaga no momento da reserva (ADR 0042)."""
    op.add_column("bookings", sa.Column("band_id", sa.Uuid(), nullable=True))
    op.add_column("bookings", sa.Column("tickets_per_seat", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_bookings_band_id_pricing_bands",
        "bookings",
        "pricing_bands",
        ["band_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "tickets_per_seat_non_negative",
        "bookings",
        "tickets_per_seat IS NULL OR tickets_per_seat >= 0",
    )
    op.create_index("ix_bookings_band_id", "bookings", ["band_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_bookings_band_id", table_name="bookings")
    op.drop_constraint(
        "tickets_per_seat_non_negative",
        "bookings",
        type_="check",
    )
    op.drop_constraint(
        "fk_bookings_band_id_pricing_bands",
        "bookings",
        type_="foreignkey",
    )
    op.drop_column("bookings", "tickets_per_seat")
    op.drop_column("bookings", "band_id")
