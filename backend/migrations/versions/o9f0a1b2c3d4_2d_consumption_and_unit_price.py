"""2D consumption table, unit price and rollback of cents-in-lot

Revision ID: o9f0a1b2c3d4
Revises: n8e9f0a1b2c3
Create Date: 2026-11-16 22:30:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "n8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STANDARD: dict[str, dict[int, int]] = {
    "economica_dia": {5: 5, 6: 4, 3: 8},
    "economica_noite": {5: 6, 6: 5, 3: 10},
    "padrao_dia": {5: 7, 6: 6, 3: 12},
    "padrao_noite": {5: 9, 6: 8, 3: 15},
    "coberta": {5: 11, 6: 9, 3: 17},
    "premium": {5: 12, 6: 10, 3: 20},
}

PREVIOUS: dict[str, dict[int, int]] = {
    "economica_dia": {5: 5, 6: 4, 4: 6, 3: 8},
    "economica_noite": {5: 6, 6: 5, 4: 8, 3: 10},
    "padrao_dia": {5: 7, 6: 6, 4: 9, 3: 12},
    "padrao_noite": {5: 9, 6: 7, 4: 11, 3: 14},
    "coberta": {5: 10, 6: 9, 4: 13, 3: 17},
    "premium": {5: 12, 6: 10, 4: 14, 3: 19},
}

PREMIUM_ACCOUNT = ("purchase_premium_deferred", "liability")


def _band_id(bind, code: str) -> object | None:  # noqa: ANN001
    return bind.execute(
        sa.text("SELECT id FROM pricing_bands WHERE code = :code AND version = 1 LIMIT 1"),
        {"code": code},
    ).scalar()


def _apply_table(bind, table: dict[str, dict[int, int]]) -> None:  # noqa: ANN001
    for code, by_team in table.items():
        band_id = _band_id(bind, code)
        if band_id is None:
            continue
        for team_size, tickets in by_team.items():
            result = bind.execute(
                sa.text(
                    "UPDATE pricing_band_tickets SET tickets = :tickets "
                    "WHERE band_id = :band_id AND team_size = :team_size"
                ),
                {"tickets": tickets, "band_id": band_id, "team_size": team_size},
            )
            if result.rowcount == 0:
                bind.execute(
                    sa.text(
                        "INSERT INTO pricing_band_tickets "
                        "(id, band_id, team_size, tickets) "
                        "VALUES (:id, :band_id, :team_size, :tickets)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "band_id": band_id,
                        "team_size": team_size,
                        "tickets": tickets,
                    },
                )


def _backfill_unit_price(bind) -> None:  # noqa: ANN001
    lots = bind.execute(
        sa.text(
            "SELECT id, user_id, ref_id FROM ticket_lots "
            "WHERE source = 'purchase' AND unit_price_cents IS NULL"
        )
    ).all()
    for lot_id, _user_id, purchase_id in lots:
        purchase = bind.execute(
            sa.text("SELECT tickets, amount_cents FROM ticket_purchases WHERE id = :id"),
            {"id": purchase_id},
        ).first()
        if purchase is None or int(purchase[0]) <= 0:
            continue
        tickets, amount = int(purchase[0]), int(purchase[1])
        unit, remainder = divmod(amount, tickets)
        if remainder != 0:
            raise RuntimeError("ticket purchase amount is not divisible by tickets")
        bind.execute(
            sa.text("UPDATE ticket_lots SET unit_price_cents = :unit WHERE id = :lot_id"),
            {"unit": unit, "lot_id": lot_id},
        )

    refunds = bind.execute(
        sa.text(
            "SELECT id, user_id FROM ticket_lots "
            "WHERE source = 'refund' AND unit_price_cents IS NULL"
        )
    ).all()
    for lot_id, user_id in refunds:
        price = bind.execute(
            sa.text(
                "SELECT MAX(unit_price_cents) FROM ticket_lots "
                "WHERE user_id = :user_id AND source IN ('purchase', 'refund')"
            ),
            {"user_id": user_id},
        ).scalar()
        if price is not None:
            bind.execute(
                sa.text("UPDATE ticket_lots SET unit_price_cents = :unit WHERE id = :lot_id"),
                {"unit": int(price), "lot_id": lot_id},
            )


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("ticket_lots", sa.Column("unit_price_cents", sa.Integer(), nullable=True))
    _backfill_unit_price(bind)
    op.create_check_constraint(
        "unit_price_positive",
        "ticket_lots",
        "unit_price_cents IS NULL OR unit_price_cents > 0",
    )

    op.drop_constraint("remaining_cents_valid", "ticket_lots", type_="check")
    op.drop_column("ticket_lots", "remaining_cents")

    # 5x5, 6x6 e 3x3 são padrão; 4x4 e menores são contingência sem célula.
    bind.execute(sa.text("DELETE FROM pricing_band_tickets WHERE team_size NOT IN (3, 5, 6)"))
    _apply_table(bind, STANDARD)

    bind.execute(
        sa.text(
            "DELETE FROM ledger_accounts WHERE code = :code AND NOT EXISTS ("
            "  SELECT 1 FROM ledger_entries e WHERE e.account_id = ledger_accounts.id"
            ")"
        ).bindparams(sa.bindparam("code", value=PREMIUM_ACCOUNT[0]))
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.add_column("ticket_lots", sa.Column("remaining_cents", sa.Integer(), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE ticket_lots SET remaining_cents = remaining * 310 "
            "WHERE source IN ('purchase', 'refund')"
        )
    )
    op.create_check_constraint(
        "remaining_cents_valid",
        "ticket_lots",
        "remaining_cents IS NULL OR remaining_cents >= 0",
    )
    op.drop_constraint("unit_price_positive", "ticket_lots", type_="check")
    op.drop_column("ticket_lots", "unit_price_cents")

    bind.execute(
        sa.text(
            "INSERT INTO ledger_accounts (id, code, kind, custody_model, created_at) "
            "SELECT :id, :code_add, :kind, 'B', now() "
            "WHERE NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE code = :code_check)"
        ),
        {
            "id": uuid.uuid4(),
            "code_add": PREMIUM_ACCOUNT[0],
            "code_check": PREMIUM_ACCOUNT[0],
            "kind": PREMIUM_ACCOUNT[1],
        },
    )

    _apply_table(bind, PREVIOUS)
