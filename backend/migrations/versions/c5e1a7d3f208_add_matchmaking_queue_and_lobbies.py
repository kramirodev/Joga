"""add matchmaking queue, lobbies and runs

Revision ID: c5e1a7d3f208
Revises: b8d2f4a6c910
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5e1a7d3f208"
down_revision: str | Sequence[str] | None = "b8d2f4a6c910"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WAITING = sa.text("status = 'waiting'")


def upgrade() -> None:
    """Cria lobbies, entradas de fila, participantes e rodadas do worker."""
    op.create_table(
        "lobbies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("court_preference", sa.String(length=20), nullable=False),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lng", sa.Float(), nullable=False),
        sa.Column("radius_km", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=True),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("origin IN ('matchmaking', 'manual')", name="origin_valid"),
        sa.CheckConstraint("mode IN ('casual', 'ranked')", name="mode_valid"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'completed')", name="status_valid"
        ),
        sa.CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        sa.CheckConstraint("scheduled_end_at > scheduled_start_at", name="time_order_valid"),
        sa.CheckConstraint("duration_minutes > 0", name="duration_positive"),
        sa.CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        sa.CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        sa.CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
        sa.ForeignKeyConstraint(
            ["format_id"],
            ["sport_formats.id"],
            name="fk_lobbies_format_id_sport_formats",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name="fk_lobbies_venue_id_venues",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lobbies"),
    )
    op.create_index("ix_lobbies_format_id", "lobbies", ["format_id"])

    op.create_table(
        "queue_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("court_preference", sa.String(length=20), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lng", sa.Float(), nullable=False),
        sa.Column("radius_km", sa.Integer(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('casual', 'ranked')", name="mode_valid"),
        sa.CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'matched', 'cancelled', 'expired')", name="status_valid"
        ),
        sa.CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        sa.CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        sa.CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        sa.CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
        sa.ForeignKeyConstraint(
            ["format_id"],
            ["sport_formats.id"],
            name="fk_queue_entries_format_id_sport_formats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name="fk_queue_entries_lobby_id_lobbies",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_queue_entries_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_queue_entries"),
    )
    op.create_index("ix_queue_entries_user_id", "queue_entries", ["user_id"])
    op.create_index("ix_queue_entries_format_id", "queue_entries", ["format_id"])
    op.create_index("ix_queue_entries_lobby_id", "queue_entries", ["lobby_id"])
    op.create_index(
        "ix_queue_entries_waiting",
        "queue_entries",
        ["format_id", "mode", "status", "created_at"],
    )
    op.create_index(
        "uq_queue_entries_active",
        "queue_entries",
        ["user_id", "format_id", "mode"],
        unique=True,
        postgresql_where=WAITING,
        sqlite_where=WAITING,
    )

    op.create_table(
        "lobby_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("queue_entry_id", sa.Uuid(), nullable=True),
        sa.Column("team", sa.SmallInteger(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("team IN (1, 2)", name="team_valid"),
        sa.CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name="fk_lobby_participants_lobby_id_lobbies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["queue_entry_id"],
            ["queue_entries.id"],
            name="fk_lobby_participants_queue_entry_id_queue_entries",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_lobby_participants_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lobby_participants"),
        sa.UniqueConstraint("lobby_id", "user_id", name="uq_lobby_participants_user"),
        sa.UniqueConstraint("queue_entry_id", name="uq_lobby_participants_entry"),
    )
    op.create_index("ix_lobby_participants_lobby_id", "lobby_participants", ["lobby_id"])
    op.create_index("ix_lobby_participants_user_id", "lobby_participants", ["user_id"])

    op.create_table(
        "matchmaking_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("entries_expired", sa.Integer(), nullable=False),
        sa.Column("lobbies_formed", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="status_valid"),
        sa.CheckConstraint("entries_expired >= 0", name="expired_non_negative"),
        sa.CheckConstraint("lobbies_formed >= 0", name="lobbies_non_negative"),
        sa.PrimaryKeyConstraint("id", name="pk_matchmaking_runs"),
    )


def downgrade() -> None:
    """Remove fila, lobbies, participantes e rodadas."""
    op.drop_table("matchmaking_runs")
    op.drop_index("ix_lobby_participants_user_id", table_name="lobby_participants")
    op.drop_index("ix_lobby_participants_lobby_id", table_name="lobby_participants")
    op.drop_table("lobby_participants")
    op.drop_index("uq_queue_entries_active", table_name="queue_entries")
    op.drop_index("ix_queue_entries_waiting", table_name="queue_entries")
    op.drop_index("ix_queue_entries_lobby_id", table_name="queue_entries")
    op.drop_index("ix_queue_entries_format_id", table_name="queue_entries")
    op.drop_index("ix_queue_entries_user_id", table_name="queue_entries")
    op.drop_table("queue_entries")
    op.drop_index("ix_lobbies_format_id", table_name="lobbies")
    op.drop_table("lobbies")
