"""add season placements

Revision ID: f5b2d8e4c310
Revises: e4a1c9d7b203
Create Date: 2026-11-13 16:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5b2d8e4c310"
down_revision: str | Sequence[str] | None = "e4a1c9d7b203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Colocação por temporada para o reset suave da divisão."""
    op.create_table(
        "season_placements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("matches_played", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("matches_played >= 0", name="matches_played_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "season_id"),
    )
    op.create_index(
        "ix_season_placements_season_played",
        "season_placements",
        ["season_id", "matches_played"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_season_placements_season_played", table_name="season_placements")
    op.drop_table("season_placements")
