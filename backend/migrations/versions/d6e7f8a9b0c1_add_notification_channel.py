"""add notification channel

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-11-15 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "channel",
            sa.String(length=20),
            server_default="player",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE notifications SET channel = 'moderation' "
        "WHERE kind IN ('moderation_report', 'moderation_appeal')"
    )
    op.create_check_constraint(
        "channel_valid",
        "notifications",
        "channel IN ('player','moderation')",
    )
    op.create_index(
        "ix_notifications_user_channel_created",
        "notifications",
        ["user_id", "channel", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_channel_created", table_name="notifications")
    op.drop_constraint("channel_valid", "notifications", type_="check")
    op.drop_column("notifications", "channel")
