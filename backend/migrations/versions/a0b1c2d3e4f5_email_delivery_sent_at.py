"""registra o instante de envio da entrega de e-mail

Revision ID: a0b1c2d3e4f5
Revises: z9c0d1e2f3a4
Create Date: 2026-11-19 03:00:00.000000

A latência da Outbox (``sent_at - created_at``) precisa sobreviver à limpeza do
payload da Outbox para permitir p50/p95 diários.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | Sequence[str] | None = "z9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_deliveries",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_email_deliveries_sent_at",
        "email_deliveries",
        ["sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_sent_at", table_name="email_deliveries")
    op.drop_column("email_deliveries", "sent_at")
