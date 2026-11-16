"""add webhook retry state

Revision ID: g0c1d2e3f4a5
Revises: f9b0c1d2e3f4
Create Date: 2026-11-15 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g0c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "f9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "psp_webhook_events",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "psp_webhook_events",
        sa.Column("last_error", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "psp_webhook_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_psp_webhook_events_retry",
        "psp_webhook_events",
        ["processed_at", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_psp_webhook_events_retry", table_name="psp_webhook_events")
    op.drop_column("psp_webhook_events", "next_attempt_at")
    op.drop_column("psp_webhook_events", "last_error")
    op.drop_column("psp_webhook_events", "attempts")
