"""drop legacy booking ledger entries

Revision ID: u5f6a7b8c9d0
Revises: t4e5f6a7b8c9
Create Date: 2026-11-17 12:30:00.000000

O extrato do fornecedor passa a ser projetado de ``ledger_transactions`` +
``ledger_entries`` (dupla entrada). A tabela single-entry
``booking_ledger_entries`` é aposentada.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "t4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_booking_ledger_entries_booking_created",
        table_name="booking_ledger_entries",
    )
    op.drop_table("booking_ledger_entries")


def downgrade() -> None:
    op.create_table(
        "booking_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("booking_payment_id", sa.Uuid(), nullable=True),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entry_type IN ("
            "'CHARGE_CREATED', 'PAYMENT_CONFIRMED', 'PAYMENT_REFUNDED', 'VENUE_RELEASE'"
            ")",
            name="ck_booking_ledger_entries_entry_type_valid",
        ),
        sa.CheckConstraint(
            "direction IN ('DEBIT', 'CREDIT')",
            name="ck_booking_ledger_entries_direction_valid",
        ),
        sa.CheckConstraint(
            "amount_cents >= 0",
            name="ck_booking_ledger_entries_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name="fk_booking_ledger_entries_booking_id_bookings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["booking_payment_id"],
            ["booking_payments.id"],
            name="fk_booking_ledger_entries_booking_payment_id_booking_payments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_booking_ledger_entries"),
        sa.UniqueConstraint(
            "booking_payment_id",
            "entry_type",
            name="uq_booking_ledger_entries_payment_type",
        ),
    )
    op.create_index(
        "ix_booking_ledger_entries_booking_created",
        "booking_ledger_entries",
        ["booking_id", "created_at"],
        unique=False,
    )
