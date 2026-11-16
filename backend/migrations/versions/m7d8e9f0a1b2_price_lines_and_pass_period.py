"""price lines on bookings and monthly pass period

Revision ID: m7d8e9f0a1b2
Revises: l6c7d8e9f0a1
Create Date: 2026-11-16 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "l6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preço em duas linhas, congelado por reserva (ADR 0049 §3.3). Reservas
    # antigas não tiveram taxa: entram como legado, com fee zero.
    op.add_column(
        "bookings",
        sa.Column("venue_price_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "bookings",
        sa.Column("fee_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "bookings",
        sa.Column("fee_percent_applied", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "bookings",
        sa.Column("total_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "pricing_version",
            sa.String(length=20),
            server_default="legacy_v0",
            nullable=False,
        ),
    )
    op.create_check_constraint("venue_price_non_negative", "bookings", "venue_price_cents >= 0")
    op.create_check_constraint("fee_non_negative", "bookings", "fee_cents >= 0")
    op.create_check_constraint(
        "fee_percent_valid", "bookings", "fee_percent_applied BETWEEN 0 AND 10000"
    )
    op.create_check_constraint(
        "total_matches_lines",
        "bookings",
        "total_cents = venue_price_cents + fee_cents",
    )
    op.execute(
        "UPDATE bookings SET venue_price_cents = price_cents, "
        "fee_cents = 0, fee_percent_applied = 0, total_cents = price_cents, "
        "pricing_version = 'legacy_v0'"
    )

    # Franquia do passe passa a ter competência mensal explícita. O crédito
    # comprado continua sem `expires_at`.
    op.add_column("ticket_lots", sa.Column("period", sa.String(length=7), nullable=True))
    op.create_index("ix_ticket_lots_user_period", "ticket_lots", ["user_id", "period"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE ticket_lots SET period = COALESCE("
            "to_char(expires_at - interval '1 month', 'YYYY-MM'), "
            "to_char(created_at, 'YYYY-MM')) "
            "WHERE source = 'pass' AND period IS NULL"
        )
    else:
        op.execute(
            "UPDATE ticket_lots SET period = COALESCE("
            "substr(expires_at, 1, 7), substr(created_at, 1, 7)) "
            "WHERE source = 'pass' AND period IS NULL"
        )
    op.create_check_constraint(
        "pass_period_required", "ticket_lots", "source <> 'pass' OR period IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint("pass_period_required", "ticket_lots", type_="check")
    op.drop_index("ix_ticket_lots_user_period", table_name="ticket_lots")
    op.drop_column("ticket_lots", "period")

    op.drop_constraint("total_matches_lines", "bookings", type_="check")
    op.drop_constraint("fee_percent_valid", "bookings", type_="check")
    op.drop_constraint("fee_non_negative", "bookings", type_="check")
    op.drop_constraint("venue_price_non_negative", "bookings", type_="check")
    op.drop_column("bookings", "pricing_version")
    op.drop_column("bookings", "total_cents")
    op.drop_column("bookings", "fee_percent_applied")
    op.drop_column("bookings", "fee_cents")
    op.drop_column("bookings", "venue_price_cents")
