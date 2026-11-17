"""credit in cents, two-line allocation and purchase premium

Revision ID: n8e9f0a1b2c3
Revises: m7d8e9f0a1b2
Create Date: 2026-11-16 21:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "m7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TICKET_VALUE_CENTS = 310
PREMIUM_ACCOUNT = ("purchase_premium_deferred", "liability")


def _allocate(total: int, parts: int) -> list[int]:
    base, remainder = divmod(total, parts)
    return [base + 1 if index < remainder else base for index in range(parts)]


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("ticket_lots", sa.Column("remaining_cents", sa.Integer(), nullable=True))
    op.add_column(
        "ticket_lot_consumptions",
        sa.Column("amount_cents", sa.Integer(), nullable=True),
    )
    op.drop_constraint("amount_positive", "ticket_lot_consumptions", type_="check")
    op.create_check_constraint("amount_non_negative", "ticket_lot_consumptions", "amount >= 0")
    op.add_column(
        "booking_participants",
        sa.Column("space_charge_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "booking_participants",
        sa.Column("fee_charge_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "booking_participants",
        sa.Column("funding_source", sa.String(length=12), nullable=True),
    )

    # Crédito comprado e devolução passam a valer R$ 3,10 por ticket. O preço
    # pago acima disso é prêmio de compra, nunca crédito (ADR 0049 §11.7).
    bind.execute(
        sa.text(
            "UPDATE ticket_lots SET remaining_cents = remaining * :value "
            "WHERE source IN ('purchase', 'refund') AND remaining_cents IS NULL"
        ),
        {"value": TICKET_VALUE_CENTS},
    )
    bind.execute(
        sa.text(
            "UPDATE ticket_lot_consumptions SET amount_cents = amount * :value "
            "WHERE amount_cents IS NULL"
        ),
        {"value": TICKET_VALUE_CENTS},
    )

    # Rateio retroativo em duas linhas. A taxa é alocada e o espaço recebe o
    # resto da cota, garantindo Σ espaço = venue_price e Σ taxa = fee.
    bookings = bind.execute(sa.text("SELECT id, venue_price_cents, fee_cents FROM bookings")).all()
    for booking_id, venue_price, fee in bookings:
        participants = bind.execute(
            sa.text(
                "SELECT id, contribution_cents FROM booking_participants "
                "WHERE booking_id = :booking_id ORDER BY seat, id"
            ),
            {"booking_id": booking_id},
        ).all()
        if not participants:
            continue
        fee_charges = _allocate(int(fee), len(participants))
        for (participant_id, contribution), fee_charge in zip(
            participants, fee_charges, strict=True
        ):
            contribution_value = int(contribution)
            fee_value = min(int(fee_charge), contribution_value)
            space_value = contribution_value - fee_value
            bind.execute(
                sa.text(
                    "UPDATE booking_participants SET space_charge_cents = :space, "
                    "fee_charge_cents = :fee WHERE id = :participant_id"
                ),
                {
                    "space": space_value,
                    "fee": fee_value,
                    "participant_id": participant_id,
                },
            )
        if sum(int(item[1]) for item in participants) != int(venue_price) + int(fee):
            raise RuntimeError("booking contribution total diverges from price lines")
        space_total = bind.execute(
            sa.text(
                "SELECT COALESCE(SUM(space_charge_cents), 0), "
                "COALESCE(SUM(fee_charge_cents), 0) "
                "FROM booking_participants WHERE booking_id = :booking_id"
            ),
            {"booking_id": booking_id},
        ).one()
        if int(space_total[0]) != int(venue_price) or int(space_total[1]) != int(fee):
            raise RuntimeError("booking allocation does not close price lines")

    # Origem de quitação. Consumo de lote não pago vem de passe/grátis/admin.
    consumed = bind.execute(
        sa.text(
            "SELECT p.id, p.user_id, p.booking_id "
            "FROM booking_participants p WHERE p.tickets_consumed > 0"
        )
    ).all()
    for participant_id, user_id, booking_id in consumed:
        sources = {
            str(row[0])
            for row in bind.execute(
                sa.text(
                    "SELECT DISTINCT l.source FROM ticket_lot_consumptions c "
                    "JOIN ticket_lots l ON l.id = c.lot_id "
                    "WHERE c.user_id = :user_id AND c.ref_id = :booking_id"
                ),
                {"user_id": user_id, "booking_id": booking_id},
            ).all()
        }
        if sources & {"pass", "free_level", "admin"}:
            source = next(item for item in ("pass", "free_level", "admin") if item in sources)
        else:
            source = "credit"
        bind.execute(
            sa.text(
                "UPDATE booking_participants SET funding_source = :source "
                "WHERE id = :participant_id"
            ),
            {"source": source, "participant_id": participant_id},
        )
    bind.execute(
        sa.text(
            "UPDATE booking_participants SET funding_source = 'pix' "
            "WHERE funding_source IS NULL AND payment_status = 'PAID'"
        )
    )

    op.create_check_constraint(
        "remaining_cents_valid", "ticket_lots", "remaining_cents IS NULL OR remaining_cents >= 0"
    )
    op.create_check_constraint(
        "amount_cents_positive",
        "ticket_lot_consumptions",
        "amount_cents IS NULL OR amount_cents > 0",
    )
    op.create_check_constraint(
        "space_charge_non_negative",
        "booking_participants",
        "space_charge_cents >= 0",
    )
    op.create_check_constraint(
        "fee_charge_non_negative",
        "booking_participants",
        "fee_charge_cents >= 0",
    )
    op.create_check_constraint(
        "charges_match_contribution",
        "booking_participants",
        "space_charge_cents + fee_charge_cents = contribution_cents",
    )
    op.create_check_constraint(
        "funding_source_valid",
        "booking_participants",
        "funding_source IS NULL OR funding_source IN "
        "('pix', 'credit', 'pass', 'free_level', 'admin')",
    )
    op.create_index(
        "ix_booking_participants_funding_source",
        "booking_participants",
        ["funding_source"],
    )

    code, kind = PREMIUM_ACCOUNT
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "INSERT INTO ledger_accounts (id, code, kind, custody_model, created_at) "
                "SELECT :id, :code_add, :kind, 'B', now() "
                "WHERE NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE code = :code_check)"
            ),
            {
                "id": uuid.uuid4(),
                "code_add": code,
                "code_check": code,
                "kind": kind,
            },
        )
    else:
        bind.execute(
            sa.text(
                "INSERT INTO ledger_accounts (id, code, kind, custody_model, created_at) "
                "SELECT :id, :code, :kind, 'B', CURRENT_TIMESTAMP "
                "WHERE NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE code = :code)"
            ),
            {"id": uuid.uuid4().hex, "code": code, "kind": kind},
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM ledger_accounts WHERE code = :code AND NOT EXISTS ("
            "  SELECT 1 FROM ledger_entries e WHERE e.account_id = ledger_accounts.id"
            ")"
        ).bindparams(sa.bindparam("code", value=PREMIUM_ACCOUNT[0]))
    )
    op.drop_index(
        "ix_booking_participants_funding_source",
        table_name="booking_participants",
    )
    op.drop_constraint("funding_source_valid", "booking_participants", type_="check")
    op.drop_constraint("charges_match_contribution", "booking_participants", type_="check")
    op.drop_constraint("fee_charge_non_negative", "booking_participants", type_="check")
    op.drop_constraint("space_charge_non_negative", "booking_participants", type_="check")
    op.drop_constraint("amount_cents_positive", "ticket_lot_consumptions", type_="check")
    op.drop_constraint("amount_non_negative", "ticket_lot_consumptions", type_="check")
    op.create_check_constraint("amount_positive", "ticket_lot_consumptions", "amount > 0")
    op.drop_constraint("remaining_cents_valid", "ticket_lots", type_="check")
    op.drop_column("booking_participants", "funding_source")
    op.drop_column("booking_participants", "fee_charge_cents")
    op.drop_column("booking_participants", "space_charge_cents")
    op.drop_column("ticket_lot_consumptions", "amount_cents")
    op.drop_column("ticket_lots", "remaining_cents")
