"""add season, xp and streak

Revision ID: b7c8394d5162
Revises: a6b7283c4051
Create Date: 2026-11-12 16:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8394d5162"
down_revision: str | Sequence[str] | None = "a6b7283c4051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria temporada, ledger de XP, projeção de nível e streak."""
    op.create_table(
        "seasons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("track_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'closed')", name="status_valid"),
        sa.CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        sa.CheckConstraint("track_version > 0", name="track_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "xp_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint(
            "source IN ('match','win','mission','new_venue','admin')", name="source_valid"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_xp_events_user_season", "xp_events", ["user_id", "season_id"])

    op.create_table(
        "season_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("xp_total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("level", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("xp_total >= 0", name="xp_non_negative"),
        sa.CheckConstraint("level >= 0", name="level_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "season_id"),
    )

    op.create_table(
        "win_streaks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("current_wins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("best_wins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_match_week", sa.Date(), nullable=True),
        sa.Column("last_match_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("current_wins >= 0", name="current_non_negative"),
        sa.CheckConstraint("best_wins >= 0", name="best_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.bulk_insert(
        sa.table(
            "seasons",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("starts_at", sa.DateTime(timezone=True)),
            sa.column("ends_at", sa.DateTime(timezone=True)),
            sa.column("status", sa.String()),
            sa.column("track_version", sa.Integer()),
        ),
        [
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, "joga-season-2026-q4"),
                "code": "2026-Q4",
                "starts_at": "2026-10-01T03:00:00+00:00",
                "ends_at": "2027-01-01T03:00:00+00:00",
                "status": "active",
                "track_version": 1,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("win_streaks")
    op.drop_table("season_progress")
    op.drop_index("ix_xp_events_user_season", table_name="xp_events")
    op.drop_table("xp_events")
    op.drop_table("seasons")
