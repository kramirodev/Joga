"""add clans

Revision ID: b7d4f1a9c620
Revises: f5b2d8e4c310
Create Date: 2026-11-13 17:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d4f1a9c620"
down_revision: str | Sequence[str] | None = "f5b2d8e4c310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Clã, membros, pedidos, troféus, chat e denúncias."""
    op.create_table(
        "clans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("tag", sa.String(length=8), nullable=False),
        sa.Column("description", sa.String(length=280), nullable=True),
        sa.Column("emblem_ref", sa.String(length=120), nullable=True),
        sa.Column(
            "join_policy",
            sa.String(length=12),
            server_default=sa.text("'approval'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "join_policy IN ('approval', 'open', 'closed')",
            name="join_policy_valid",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="status_valid"),
        sa.CheckConstraint("length(name) BETWEEN 3 AND 40", name="name_length_valid"),
        sa.CheckConstraint("length(tag) BETWEEN 2 AND 8", name="tag_length_valid"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("tag"),
    )

    op.create_table(
        "clan_members",
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=10),
            server_default=sa.text("'member'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=10),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="role_valid"),
        sa.CheckConstraint("status IN ('active', 'left', 'removed')", name="status_valid"),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("clan_id", "user_id"),
    )
    op.create_index("ix_clan_members_user_status", "clan_members", ["user_id", "status"])
    op.create_index(
        "uq_clan_members_user_active",
        "clan_members",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "clan_join_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("message", sa.String(length=200), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="status_valid",
        ),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clan_join_requests_clan_status",
        "clan_join_requests",
        ["clan_id", "status"],
    )
    op.create_index(
        "uq_clan_join_requests_pending",
        "clan_join_requests",
        ["clan_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "clan_trophy_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=True),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("points >= 0", name="points_non_negative"),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["format_id"], ["sport_formats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "user_id", name="uq_clan_trophy_match_user"),
    )
    op.create_index(
        "ix_clan_trophy_clan_season_format",
        "clan_trophy_events",
        ["clan_id", "season_id", "format_id"],
    )

    op.create_table(
        "clan_trophy_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("points >= 0", name="points_non_negative"),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["format_id"], ["sport_formats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clan_id", "season_id", "format_id", name="uq_clan_trophy_snapshot"),
    )
    op.create_index(
        "ix_clan_trophy_snapshot_season",
        "clan_trophy_snapshots",
        ["season_id", "format_id"],
    )

    op.create_table(
        "clan_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(body) BETWEEN 1 AND 2000", name="body_length_valid"),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hidden_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clan_messages_clan_created", "clan_messages", ["clan_id", "created_at"])

    op.create_table(
        "clan_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column(
            "status",
            sa.String(length=14),
            server_default=sa.text("'OPEN'"),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'KEEP_HIDDEN', 'RESTORED', 'DISMISSED')",
            name="status_valid",
        ),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["clan_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "reporter_id", name="uq_clan_report_message_reporter"),
    )
    op.create_index("ix_clan_reports_clan_status", "clan_reports", ["clan_id", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_clan_reports_clan_status", table_name="clan_reports")
    op.drop_table("clan_reports")
    op.drop_index("ix_clan_messages_clan_created", table_name="clan_messages")
    op.drop_table("clan_messages")
    op.drop_index("ix_clan_trophy_snapshot_season", table_name="clan_trophy_snapshots")
    op.drop_table("clan_trophy_snapshots")
    op.drop_index("ix_clan_trophy_clan_season_format", table_name="clan_trophy_events")
    op.drop_table("clan_trophy_events")
    op.drop_index("uq_clan_join_requests_pending", table_name="clan_join_requests")
    op.drop_index("ix_clan_join_requests_clan_status", table_name="clan_join_requests")
    op.drop_table("clan_join_requests")
    op.drop_index("uq_clan_members_user_active", table_name="clan_members")
    op.drop_index("ix_clan_members_user_status", table_name="clan_members")
    op.drop_table("clan_members")
    op.drop_table("clans")
