"""add provider status detail to payment views

Revision ID: h1d2e3f4a5b6
Revises: g0c1d2e3f4a5
Create Date: 2026-11-15 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "g0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_payments",
        sa.Column("provider_status_detail", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "purchase_payments",
        sa.Column("provider_status_detail", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_payments", "provider_status_detail")
    op.drop_column("booking_payments", "provider_status_detail")
