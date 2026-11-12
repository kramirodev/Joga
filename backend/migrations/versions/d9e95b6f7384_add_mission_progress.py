"""add mission progress

Revision ID: d9e95b6f7384
Revises: c8d94a5e6273
Create Date: 2026-11-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e95b6f7384"
down_revision: str | Sequence[str] | None = "c8d94a5e6273"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Progresso semanal de missão. Uma linha por semana, sem rotina destrutiva."""
    op.create_table(
        "mission_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("mission_code", sa.String(length=30), nullable=False),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress >= 0", name="progress_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "season_id", "week_start", "mission_code"),
    )
    op.create_index(
        "ix_mission_progress_user_week",
        "mission_progress",
        ["user_id", "week_start"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_mission_progress_user_week", table_name="mission_progress")
    op.drop_table("mission_progress")
