"""add double-entry ledger

Revision ID: j3f4a5b6c7d8
Revises: i2e3f4a5b6c7
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "i2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BALANCE_VIEW = """
CREATE VIEW v_ledger_balances AS
SELECT
    a.id AS account_id,
    a.code,
    a.kind,
    a.owner_kind,
    a.owner_id,
    COALESCE(SUM(CASE WHEN e.direction = 'D' THEN e.amount_cents ELSE 0 END), 0)
        AS debit_cents,
    COALESCE(SUM(CASE WHEN e.direction = 'C' THEN e.amount_cents ELSE 0 END), 0)
        AS credit_cents,
    CASE
        WHEN a.kind IN ('asset', 'expense')
        THEN COALESCE(SUM(CASE WHEN e.direction = 'D' THEN e.amount_cents ELSE 0 END), 0)
           - COALESCE(SUM(CASE WHEN e.direction = 'C' THEN e.amount_cents ELSE 0 END), 0)
        ELSE COALESCE(SUM(CASE WHEN e.direction = 'C' THEN e.amount_cents ELSE 0 END), 0)
           - COALESCE(SUM(CASE WHEN e.direction = 'D' THEN e.amount_cents ELSE 0 END), 0)
    END AS balance_cents
FROM ledger_accounts a
LEFT JOIN ledger_entries e ON e.account_id = a.id
GROUP BY a.id, a.code, a.kind, a.owner_kind, a.owner_id
"""

BALANCE_TRIGGER = """
CREATE OR REPLACE FUNCTION joga_ledger_balance_guard() RETURNS trigger AS $$
DECLARE
    target uuid;
    debits bigint;
    credits bigint;
BEGIN
    target := NEW.transaction_id;
    SELECT
        COALESCE(SUM(CASE WHEN direction = 'D' THEN amount_cents ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN direction = 'C' THEN amount_cents ELSE 0 END), 0)
    INTO debits, credits
    FROM ledger_entries
    WHERE transaction_id = target;
    IF debits <> credits THEN
        RAISE EXCEPTION 'ledger transaction % unbalanced (D=%, C=%)',
            target, debits, credits;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER joga_ledger_balance_guard
AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION joga_ledger_balance_guard()
"""

IMMUTABLE_TRIGGER = """
CREATE OR REPLACE FUNCTION joga_ledger_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER joga_ledger_reject_mutation
BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION joga_ledger_reject_mutation()
"""


def upgrade() -> None:
    # A tabela antiga era o ledger da reserva, não o ledger contábil. Renomear
    # libera `ledger_entries` para o novo modelo sem perder histórico.
    op.rename_table("ledger_entries", "booking_ledger_entries")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER INDEX pk_ledger_entries RENAME TO pk_booking_ledger_entries")
        op.execute(
            "ALTER INDEX uq_ledger_entries_payment_type "
            "RENAME TO uq_booking_ledger_entries_payment_type"
        )
        op.execute(
            "ALTER INDEX ix_ledger_entries_booking_created "
            "RENAME TO ix_booking_ledger_entries_booking_created"
        )

    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("owner_kind", sa.String(length=10), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("custody_model", sa.String(length=1), server_default="B", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('asset', 'liability', 'revenue', 'expense', 'equity')",
            name="kind_valid",
        ),
        sa.CheckConstraint(
            "owner_kind IS NULL OR owner_kind IN ('user', 'venue', 'joga')",
            name="owner_kind_valid",
        ),
        sa.CheckConstraint(
            "(owner_kind IS NULL) = (owner_id IS NULL)",
            name="owner_pair_valid",
        ),
        sa.CheckConstraint("custody_model IN ('B', 'C')", name="custody_model_valid"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("custody_model", sa.String(length=1), nullable=False),
        sa.Column("reverses_transaction_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("custody_model IN ('B', 'C')", name="custody_model_valid"),
        sa.ForeignKeyConstraint(
            ["reverses_transaction_id"],
            ["ledger_transactions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_ledger_transactions_ref",
        "ledger_transactions",
        ["ref_type", "ref_id"],
    )
    op.create_index(
        "ix_ledger_transactions_occurred",
        "ledger_transactions",
        ["occurred_at"],
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=1), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("direction IN ('D', 'C')", name="direction_valid"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["ledger_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["ledger_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_entries_account", "ledger_entries", ["account_id"])
    op.create_index("ix_ledger_entries_transaction", "ledger_entries", ["transaction_id"])
    op.create_index(
        "uq_ledger_entries_transaction_account_direction",
        "ledger_entries",
        ["transaction_id", "account_id", "direction"],
        unique=True,
    )
    op.execute(BALANCE_VIEW)
    if op.get_bind().dialect.name == "postgresql":
        op.execute(BALANCE_TRIGGER)
        op.execute(IMMUTABLE_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS joga_ledger_reject_mutation ON ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS joga_ledger_reject_mutation()")
        op.execute("DROP TRIGGER IF EXISTS joga_ledger_balance_guard ON ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS joga_ledger_balance_guard()")
    op.execute("DROP VIEW IF EXISTS v_ledger_balances")
    op.drop_index(
        "uq_ledger_entries_transaction_account_direction",
        table_name="ledger_entries",
    )
    op.drop_index("ix_ledger_entries_transaction", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_account", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_ledger_transactions_occurred", table_name="ledger_transactions")
    op.drop_index("ix_ledger_transactions_ref", table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
    op.drop_table("ledger_accounts")
    op.rename_table("booking_ledger_entries", "ledger_entries")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER INDEX pk_booking_ledger_entries RENAME TO pk_ledger_entries")
        op.execute(
            "ALTER INDEX uq_booking_ledger_entries_payment_type "
            "RENAME TO uq_ledger_entries_payment_type"
        )
        op.execute(
            "ALTER INDEX ix_booking_ledger_entries_booking_created "
            "RENAME TO ix_ledger_entries_booking_created"
        )
