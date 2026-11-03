"""add session access tokens and receipt usage

Revision ID: d4a7f2c9e610
Revises: 3c9d51a7e2b4
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a7f2c9e610"
down_revision: str | Sequence[str] | None = "3c9d51a7e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona access token opaco e marcação de recibo consumido."""
    op.add_column(
        "sessions",
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
    )
    op.add_column(
        "sessions",
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_sessions_access_token_hash",
        "sessions",
        ["access_token_hash"],
        unique=True,
    )
    op.add_column(
        "phone_challenges",
        sa.Column("receipt_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove as colunas adicionadas."""
    op.drop_index("uq_sessions_access_token_hash", table_name="sessions")
    op.drop_column("sessions", "access_expires_at")
    op.drop_column("sessions", "access_token_hash")
    op.drop_column("phone_challenges", "receipt_used_at")
