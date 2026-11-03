"""add matches, participants and state transitions

Revision ID: d7f2b9c4e615
Revises: c5e1a7d3f208
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f2b9c4e615"
down_revision: str | Sequence[str] | None = "c5e1a7d3f208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria partidas, participantes e trilha de transições."""
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_in_opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_in_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("substitution_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_reason", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "state IN ('PENDING_CONFIRMATION', 'READY', 'IN_PROGRESS', 'RESULT_PENDING', "
            "'FINALIZED', 'DISPUTED', 'VOIDED', 'CANCELLED', 'EXPIRED')",
            name="state_valid",
        ),
        sa.CheckConstraint("scheduled_end_at > scheduled_start_at", name="time_order_valid"),
        sa.CheckConstraint(
            "confirmation_deadline <= scheduled_start_at",
            name="confirmation_before_start",
        ),
        sa.CheckConstraint("check_in_opens_at <= check_in_deadline", name="checkin_order_valid"),
        sa.CheckConstraint(
            "check_in_deadline <= substitution_deadline",
            name="substitution_order_valid",
        ),
        sa.CheckConstraint(
            "substitution_deadline <= scheduled_start_at",
            name="substitution_before_start",
        ),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name="fk_matches_lobby_id_lobbies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
        sa.UniqueConstraint("lobby_id", name="uq_matches_lobby_id"),
    )

    op.create_table(
        "match_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team", sa.SmallInteger(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_substitute", sa.Boolean(), nullable=False),
        sa.Column("queue_entry_id", sa.Uuid(), nullable=True),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("team IN (1, 2)", name="team_valid"),
        sa.CheckConstraint(
            "status IN ('invited', 'confirmed', 'declined', 'checked_in', 'no_show')",
            name="status_valid",
        ),
        sa.CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_participants_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["queue_entry_id"],
            ["queue_entries.id"],
            name="fk_match_participants_queue_entry_id_queue_entries",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_match_participants_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_participants"),
        sa.UniqueConstraint("match_id", "user_id", name="uq_match_participants_user"),
    )
    op.create_index("ix_match_participants_user_id", "match_participants", ["user_id"])
    op.create_index(
        "ix_match_participants_match_status", "match_participants", ["match_id", "status"]
    )

    op.create_table(
        "match_state_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(length=24), nullable=True),
        sa.Column("to_state", sa.String(length=24), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("to_state <> ''", name="to_state_not_empty"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_match_state_transitions_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_state_transitions_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_state_transitions"),
    )
    op.create_index(
        "ix_match_state_transitions_match", "match_state_transitions", ["match_id", "created_at"]
    )


def downgrade() -> None:
    """Remove partidas, participantes e transições."""
    op.drop_index("ix_match_state_transitions_match", table_name="match_state_transitions")
    op.drop_table("match_state_transitions")
    op.drop_index("ix_match_participants_match_status", table_name="match_participants")
    op.drop_index("ix_match_participants_user_id", table_name="match_participants")
    op.drop_table("match_participants")
    op.drop_table("matches")
