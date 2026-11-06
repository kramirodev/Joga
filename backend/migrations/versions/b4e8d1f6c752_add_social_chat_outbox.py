"""add social, chat and outbox tables

Revision ID: b4e8d1f6c752
Revises: a3f7c9e2d641
Create Date: 2026-11-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4e8d1f6c752"
down_revision: str | Sequence[str] | None = "a3f7c9e2d641"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria amizades, bloqueios, convites, chat, push e Outbox."""
    op.create_table(
        "friendships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_low_id", sa.Uuid(), nullable=False),
        sa.Column("user_high_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
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
        sa.CheckConstraint("user_low_id <> user_high_id", name="distinct_users"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REMOVED')",
            name="status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_friendships_requested_by_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_high_id"],
            ["users.id"],
            name="fk_friendships_user_high_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_low_id"],
            ["users.id"],
            name="fk_friendships_user_low_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_friendships"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friendship_pair"),
    )
    op.create_index(
        "ix_friendship_high_status",
        "friendships",
        ["user_high_id", "status"],
    )
    op.create_index(
        "ix_friendship_low_status",
        "friendships",
        ["user_low_id", "status"],
    )

    op.create_table(
        "user_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("blocker_id <> blocked_id", name="distinct_users"),
        sa.ForeignKeyConstraint(
            ["blocked_id"],
            ["users.id"],
            name="fk_user_blocks_blocked_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["blocker_id"],
            ["users.id"],
            name="fk_user_blocks_blocker_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_blocks"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
    )
    op.create_index("ix_user_block_blocked", "user_blocks", ["blocked_id"])

    op.create_table(
        "lobby_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_id", sa.Uuid(), nullable=False),
        sa.Column("invitee_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("inviter_id <> invitee_id", name="distinct_users"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED')",
            name="status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["invitee_id"],
            ["users.id"],
            name="fk_lobby_invites_invitee_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inviter_id"],
            ["users.id"],
            name="fk_lobby_invites_inviter_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name="fk_lobby_invites_lobby_id_lobbies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lobby_invites"),
        sa.UniqueConstraint("lobby_id", "invitee_id", name="uq_lobby_invite_invitee"),
    )
    op.create_index(
        "ix_lobby_invite_invitee_status",
        "lobby_invites",
        ["invitee_id", "status"],
    )

    op.create_table(
        "lobby_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(body) BETWEEN 1 AND 2000", name="body_length_valid"),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name="fk_lobby_messages_lobby_id_lobbies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name="fk_lobby_messages_sender_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lobby_messages"),
    )
    op.create_index(
        "ix_lobby_message_lobby_created",
        "lobby_messages",
        ["lobby_id", "created_at"],
    )

    op.create_table(
        "device_push_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("platform IN ('android', 'ios', 'web')", name="platform_valid"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_device_push_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_device_push_tokens"),
        sa.UniqueConstraint("token", name="uq_device_push_token"),
    )
    op.create_index(
        "ix_device_push_tokens_user_id",
        "device_push_tokens",
        ["user_id"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("aggregate_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DISPATCHED', 'FAILED')",
            name="status_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
    )
    op.create_index(
        "ix_outbox_status_available",
        "outbox_events",
        ["status", "available_at"],
    )


def downgrade() -> None:
    """Remove as tabelas sociais, de chat e da Outbox."""
    op.drop_index("ix_outbox_status_available", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_device_push_tokens_user_id", table_name="device_push_tokens")
    op.drop_table("device_push_tokens")
    op.drop_index("ix_lobby_message_lobby_created", table_name="lobby_messages")
    op.drop_table("lobby_messages")
    op.drop_index("ix_lobby_invite_invitee_status", table_name="lobby_invites")
    op.drop_table("lobby_invites")
    op.drop_index("ix_user_block_blocked", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_index("ix_friendship_low_status", table_name="friendships")
    op.drop_index("ix_friendship_high_status", table_name="friendships")
    op.drop_table("friendships")
