"""add promo expense account for pass/free/admin seats

Revision ID: p0a1b2c3d4e5
Revises: o9f0a1b2c3d4
Create Date: 2026-11-17 09:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "o9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROMO_ACCOUNT = ("promo_expense", "expense")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "INSERT INTO ledger_accounts (id, code, kind, custody_model, created_at) "
                "SELECT :id, :code_add, :kind, 'B', now() "
                "WHERE NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE code = :code_check)"
            ),
            {
                "id": uuid.uuid4(),
                "code_add": PROMO_ACCOUNT[0],
                "code_check": PROMO_ACCOUNT[0],
                "kind": PROMO_ACCOUNT[1],
            },
        )
    else:
        bind.execute(
            sa.text(
                "INSERT INTO ledger_accounts (id, code, kind, custody_model, created_at) "
                "SELECT :id, :code_add, :kind, 'B', CURRENT_TIMESTAMP "
                "WHERE NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE code = :code_check)"
            ),
            {
                "id": uuid.uuid4().hex,
                "code_add": PROMO_ACCOUNT[0],
                "code_check": PROMO_ACCOUNT[0],
                "kind": PROMO_ACCOUNT[1],
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM ledger_accounts WHERE code = :code AND NOT EXISTS ("
            "  SELECT 1 FROM ledger_entries e WHERE e.account_id = ledger_accounts.id"
            ")"
        ).bindparams(sa.bindparam("code", value=PROMO_ACCOUNT[0]))
    )
