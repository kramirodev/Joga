"""allow partial payment refunds

Revision ID: s3d4e5f6a7b8
Revises: r2c3d4e5f6a7
Create Date: 2026-11-17 10:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "r2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Schema preparado para reembolso parcial sem mudar o comportamento atual:
    # todo reembolso criado pelo serviço continua FULL, e a unicidade de FULL por
    # cobrança é mantida por índice parcial.
    op.add_column(
        "payment_refunds",
        sa.Column(
            "refund_type",
            sa.String(length=10),
            server_default=sa.text("'FULL'"),
            nullable=False,
        ),
    )
    op.add_column(
        "payment_refunds",
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
    )
    op.create_check_constraint(
        "refund_type_valid",
        "payment_refunds",
        "refund_type IN ('FULL', 'PARTIAL')",
    )
    op.drop_constraint("uq_payment_refunds_payment", "payment_refunds", type_="unique")
    op.create_index(
        "uq_payment_refunds_full_payment",
        "payment_refunds",
        ["booking_payment_id"],
        unique=True,
        postgresql_where=sa.text("refund_type = 'FULL'"),
        sqlite_where=sa.text("refund_type = 'FULL'"),
    )
    op.create_index(
        "uq_payment_refunds_idempotency_key",
        "payment_refunds",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    # Não há fluxo que crie PARTIAL nesta etapa; se houver linhas parciais, o
    # downgrade as remove para restaurar a unicidade por cobrança.
    op.execute("DELETE FROM payment_refunds WHERE refund_type = 'PARTIAL'")
    op.drop_index("uq_payment_refunds_idempotency_key", table_name="payment_refunds")
    op.drop_index("uq_payment_refunds_full_payment", table_name="payment_refunds")
    op.create_unique_constraint(
        "uq_payment_refunds_payment",
        "payment_refunds",
        ["booking_payment_id"],
    )
    op.drop_constraint("refund_type_valid", "payment_refunds", type_="check")
    op.drop_column("payment_refunds", "idempotency_key")
    op.drop_column("payment_refunds", "refund_type")
