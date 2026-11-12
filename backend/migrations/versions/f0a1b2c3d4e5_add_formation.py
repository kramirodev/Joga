"""add booking formation fields

Revision ID: f0a1b2c3d4e5
Revises: e9a0b1c2d3e4
Create Date: 2026-11-09 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bookings",
        sa.Column("players_per_team", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("formation_note", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bookings", "formation_note")
    op.drop_column("bookings", "players_per_team")
