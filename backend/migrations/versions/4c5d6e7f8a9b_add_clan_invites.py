"""add clan invites

Revision ID: 4c5d6e7f8a9b
Revises: 3b25be23dfba
Create Date: 2026-11-21 10:00:00.000000

Convite direto de clã para amigo aceito, com prazo de sete dias. O índice único
parcial ``uq_clan_invites_pending`` impede dois convites pendentes do mesmo clã
para a mesma pessoa sem apagar o histórico de convites respondidos.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "4c5d6e7f8a9b"
down_revision: str | None = "3b25be23dfba"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "clan_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clan_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_id", sa.Uuid(), nullable=False),
        sa.Column("invitee_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=10),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired')",
            name="status_valid",
        ),
        sa.CheckConstraint("inviter_id <> invitee_id", name="distinct_users"),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clan_invites_invitee_status",
        "clan_invites",
        ["invitee_id", "status"],
    )
    op.create_index(
        "ix_clan_invites_clan_status",
        "clan_invites",
        ["clan_id", "status"],
    )
    op.create_index(
        "uq_clan_invites_pending",
        "clan_invites",
        ["clan_id", "invitee_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_clan_invites_pending", table_name="clan_invites")
    op.drop_index("ix_clan_invites_clan_status", table_name="clan_invites")
    op.drop_index("ix_clan_invites_invitee_status", table_name="clan_invites")
    op.drop_table("clan_invites")
