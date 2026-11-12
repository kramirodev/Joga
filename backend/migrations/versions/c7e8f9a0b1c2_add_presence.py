"""add booking presence

Revision ID: c7e8f9a0b1c2
Revises: b6d7e8f9a0b1
Create Date: 2026-11-09 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "b6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bookings",
        sa.Column("presence_closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column("pre_checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column(
            "presence_status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column(
        "booking_participants",
        sa.Column("presence_method", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column("presence_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column("presence_distance_m", sa.Integer(), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column("presence_accuracy_m", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_booking_participants_presence_status_valid"),
        "booking_participants",
        "presence_status IN ('PENDING', 'PRESENT', 'UNVERIFIED', 'NO_SHOW')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_booking_participants_presence_status_valid"),
        "booking_participants",
        type_="check",
    )
    op.drop_column("booking_participants", "presence_accuracy_m")
    op.drop_column("booking_participants", "presence_distance_m")
    op.drop_column("booking_participants", "presence_confirmed_at")
    op.drop_column("booking_participants", "presence_method")
    op.drop_column("booking_participants", "presence_status")
    op.drop_column("booking_participants", "pre_checked_in_at")
    op.drop_column("bookings", "presence_closed_at")
