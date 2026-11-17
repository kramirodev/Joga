"""persist dispute deadline snapshot

Revision ID: v6a7b8c9d0e1
Revises: u5f6a7b8c9d0
Create Date: 2026-11-17 16:00:00.000000

A janela de contestação passa a ser um snapshot persistido: ``eligible_at`` +
``JOGA_DISPUTE_WINDOW_HOURS`` no instante da criação da liberação e cópia na
contestação. Mudar a configuração não altera prazos já gravados.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "u5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "venue_releases",
        sa.Column("dispute_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE venue_releases "
        "SET dispute_deadline = eligible_at + interval '72 hours' "
        "WHERE dispute_deadline IS NULL"
    )
    op.alter_column("venue_releases", "dispute_deadline", nullable=False)

    op.add_column(
        "financial_disputes",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE financial_disputes AS d "
        "SET deadline_at = COALESCE("
        "  (SELECT r.dispute_deadline FROM venue_releases AS r WHERE r.id = d.release_id), "
        "  d.created_at + interval '72 hours'"
        ") "
        "WHERE d.deadline_at IS NULL"
    )
    op.alter_column("financial_disputes", "deadline_at", nullable=False)


def downgrade() -> None:
    op.drop_column("financial_disputes", "deadline_at")
    op.drop_column("venue_releases", "dispute_deadline")
