"""verificação de CNPJ das organizações

Revision ID: 6f1a2b3c4d5e
Revises: 4c5d6e7f8a9b
Create Date: 2026-11-21 12:00:00.000000

Adiciona a identidade empresarial verificada da organização (ADR 0062). O CNPJ
é normalizado em 14 dígitos e único; ``verification_status`` nasce ``pending``
para organizações existentes, exceto a organização da plataforma, que opera as
quadras públicas sem CNPJ de fornecedor. ``cnpj_next_check_at`` agenda a
reverificação em sete dias contados do cadastro, de forma staggered.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6f1a2b3c4d5e"
down_revision: str | None = "4c5d6e7f8a9b"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("cnpj", sa.String(length=14), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("cnpj_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("cnpj_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("cnpj_next_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("cnpj_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "verification_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "verification_status_valid",
        "organizations",
        "verification_status IN ('pending', 'verified', 'invalid')",
    )
    op.create_index(
        "uq_organizations_cnpj",
        "organizations",
        ["cnpj"],
        unique=True,
    )
    op.create_index(
        "ix_organizations_cnpj_next_check_at",
        "organizations",
        ["cnpj_next_check_at"],
    )
    # A plataforma é o próprio JOGA; não é fornecedor e não passa pelo CNPJ.
    op.execute(
        "UPDATE organizations SET verification_status = 'verified' WHERE is_platform IS TRUE"
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_cnpj_next_check_at", table_name="organizations")
    op.drop_index("uq_organizations_cnpj", table_name="organizations")
    op.drop_constraint("verification_status_valid", "organizations", type_="check")
    op.drop_column("organizations", "verification_status")
    op.drop_column("organizations", "cnpj_snapshot")
    op.drop_column("organizations", "cnpj_next_check_at")
    op.drop_column("organizations", "cnpj_verified_at")
    op.drop_column("organizations", "cnpj_status")
    op.drop_column("organizations", "cnpj")
