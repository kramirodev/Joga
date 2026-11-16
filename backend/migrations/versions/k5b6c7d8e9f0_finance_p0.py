"""finance P0: participant status, purchase idempotency, webhook hash

Revision ID: k5b6c7d8e9f0
Revises: j3f4a5b6c7d8
Create Date: 2026-11-16 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k5b6c7d8e9f0"
down_revision: str | Sequence[str] | None = "j3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYMENT_STATUSES = "'PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED', 'EXPIRED', 'CANCELLED'"
PREVIOUS_PAYMENT_STATUSES = "'PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED'"


def upgrade() -> None:
    op.drop_constraint("payment_status_valid", "booking_participants", type_="check")
    op.create_check_constraint(
        "payment_status_valid",
        "booking_participants",
        f"payment_status IN ({PAYMENT_STATUSES})",
    )

    op.add_column(
        "psp_webhook_events",
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
    )

    # Mantém apenas a compra pendente mais recente por jogador/pacote antes do
    # índice único parcial.
    op.execute(
        "UPDATE ticket_purchases AS p SET status = 'cancelled' "
        "WHERE p.status = 'pending' AND EXISTS ("
        "  SELECT 1 FROM ticket_purchases AS q "
        "  WHERE q.status = 'pending' AND q.user_id = p.user_id "
        "    AND q.pack_id = p.pack_id "
        "    AND (q.created_at > p.created_at "
        "         OR (q.created_at = p.created_at AND q.id > p.id))"
        ")"
    )
    op.create_index(
        "uq_ticket_purchases_pending_pack",
        "ticket_purchases",
        ["user_id", "pack_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_ticket_purchases_pending_pack", table_name="ticket_purchases")
    op.drop_column("psp_webhook_events", "payload_hash")
    op.drop_constraint("payment_status_valid", "booking_participants", type_="check")
    op.create_check_constraint(
        "payment_status_valid",
        "booking_participants",
        f"payment_status IN ({PREVIOUS_PAYMENT_STATUSES})",
    )
