"""seed ledger chart of accounts

Revision ID: l6c7d8e9f0a1
Revises: k5b6c7d8e9f0
Create Date: 2026-11-16 19:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l6c7d8e9f0a1"
down_revision: str | Sequence[str] | None = "k5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNTS: tuple[tuple[str, str], ...] = (
    ("psp_clearing", "asset"),
    ("bank", "asset"),
    ("fee_revenue", "revenue"),
    ("pass_deferred_revenue", "liability"),
    ("pass_revenue", "revenue"),
    ("tax_payable", "liability"),
    ("tax_expense", "expense"),
    ("psp_fee_expense", "expense"),
    ("writeoff_expense", "expense"),
    ("opening_equity", "equity"),
)

ACCOUNTS_TABLE = sa.table(
    "ledger_accounts",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("kind", sa.String()),
    sa.column("custody_model", sa.String()),
)


def upgrade() -> None:
    op.bulk_insert(
        ACCOUNTS_TABLE,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "kind": kind,
                "custody_model": "B",
            }
            for code, kind in ACCOUNTS
        ],
    )


def downgrade() -> None:
    codes = tuple(code for code, _kind in ACCOUNTS)
    op.execute(
        sa.text(
            "DELETE FROM ledger_accounts WHERE code IN :codes AND NOT EXISTS ("
            "  SELECT 1 FROM ledger_entries e WHERE e.account_id = ledger_accounts.id"
            ")"
        ).bindparams(sa.bindparam("codes", expanding=True, value=codes))
    )
