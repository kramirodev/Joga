"""add organization payout destination

Revision ID: c2d3e4f50618
Revises: a1c2e3f40517
Create Date: 2026-11-12 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f50618"
down_revision: str | Sequence[str] | None = "a1c2e3f40517"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona CNPJ, chave Pix e estado de repasse do estabelecimento."""
    op.add_column("organizations", sa.Column("legal_document", sa.String(length=14), nullable=True))
    op.add_column("organizations", sa.Column("pix_key_type", sa.String(length=10), nullable=True))
    op.add_column("organizations", sa.Column("pix_key", sa.String(length=77), nullable=True))
    op.add_column(
        "organizations",
        sa.Column(
            "payout_status",
            sa.String(length=12),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("payout_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "payout_status_valid",
        "organizations",
        "payout_status IN ('pending', 'active', 'blocked')",
    )
    op.create_check_constraint(
        "pix_key_pair_valid",
        "organizations",
        "(pix_key IS NULL AND pix_key_type IS NULL) "
        "OR (pix_key IS NOT NULL AND pix_key_type IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("pix_key_pair_valid", "organizations", type_="check")
    op.drop_constraint("payout_status_valid", "organizations", type_="check")
    op.drop_column("organizations", "payout_verified_at")
    op.drop_column("organizations", "payout_status")
    op.drop_column("organizations", "pix_key")
    op.drop_column("organizations", "pix_key_type")
    op.drop_column("organizations", "legal_document")
