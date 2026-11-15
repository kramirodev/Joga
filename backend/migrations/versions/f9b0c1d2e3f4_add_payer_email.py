"""add payer email to users and payment snapshots

Revision ID: f9b0c1d2e3f4
Revises: e7f8a9b0c1d2
Create Date: 2026-11-15 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column(
        "booking_payments",
        sa.Column("payer_email", sa.String(length=254), nullable=True),
    )
    op.add_column(
        "purchase_payments",
        sa.Column("payer_email", sa.String(length=254), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_payments", "payer_email")
    op.drop_column("booking_payments", "payer_email")
    op.drop_column("users", "email")
