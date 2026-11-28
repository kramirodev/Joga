"""assinatura: catálogo, ciclos mensais e fim da venda avulsa

Revision ID: ab12cd34ef56
Revises: z9c0d1e2f3a4
Create Date: 2026-11-27 00:00:00.000000

Aditiva para o passe legado: preserva assinaturas, entregas e créditos já
comprados. Cria o catálogo da ADR 0070, converte o contrato para 1/3/6 meses,
dá janela explícita a cada ciclo e desativa a venda de pacotes sem apagar o
histórico. Não emite documento fiscal.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ab12cd34ef56"
down_revision: str | Sequence[str] | None = "z9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabela aprovada da ADR 0070 §3. Mantida aqui porque migração não importa app.
PASS_PLANS: tuple[tuple[str, str, int, int, int], ...] = (
    ("mensal_20", "Mensal 20", 1, 20, 340),
    ("mensal_40", "Mensal 40", 1, 40, 320),
    ("mensal_60", "Mensal 60", 1, 60, 310),
    ("trimestral_20", "Trimestral 20", 3, 20, 320),
    ("trimestral_40", "Trimestral 40", 3, 40, 310),
    ("trimestral_60", "Trimestral 60", 3, 60, 300),
    ("semestral_40", "Semestral 40", 6, 40, 300),
)


def _seed_plan(code: str, label: str, months: int, tickets: int, unit_price: int) -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO pass_plans (
                id, code, label, months, tickets_per_month, unit_price_cents,
                cycle_amount_cents, installments, active, catalog_version
            ) VALUES (
                :id, :code, :label, :months, :tickets, :unit_price,
                :cycle_amount, 1, true, 1
            )
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"joga:pass_plan:{code}"),
            "code": code,
            "label": label,
            "months": months,
            "tickets": tickets,
            "unit_price": unit_price,
            "cycle_amount": tickets * months * unit_price,
        },
    )


def upgrade() -> None:
    op.create_table(
        "pass_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("months", sa.SmallInteger(), nullable=False),
        sa.Column("tickets_per_month", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("cycle_amount_cents", sa.Integer(), nullable=False),
        sa.Column("installments", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("catalog_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("months IN (1, 3, 6)", name="months_valid"),
        sa.CheckConstraint("tickets_per_month > 0", name="tickets_positive"),
        sa.CheckConstraint("unit_price_cents BETWEEN 300 AND 370", name="unit_price_range"),
        sa.CheckConstraint(
            "cycle_amount_cents = tickets_per_month * months * unit_price_cents",
            name="cycle_amount_matches",
        ),
        sa.CheckConstraint("installments = 1", name="installments_valid"),
        sa.CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_pass_plans_code"),
    )
    op.create_index(
        "ix_pass_plans_active_size",
        "pass_plans",
        ["active", "months", "tickets_per_month"],
    )
    for code, label, months, tickets, unit_price in PASS_PLANS:
        _seed_plan(code, label, months, tickets, unit_price)

    # --- assinaturas -----------------------------------------------------
    op.add_column(
        "pass_subscriptions",
        sa.Column("cycle_months", sa.SmallInteger(), server_default=sa.text("3"), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("unit_price_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("installments", sa.SmallInteger(), server_default=sa.text("1"), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("renewal_of_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("cancel_reason", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pass_subscriptions",
        sa.Column("refund_window_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_pass_subscriptions_renewal_of",
        "pass_subscriptions",
        "pass_subscriptions",
        ["renewal_of_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Legado é trimestral a R$ 3,25/ticket. O clamp evita derrubar a migração
    # por dado antigo fora da faixa, mas não cria preço novo para o catálogo.
    op.execute(
        """
        UPDATE pass_subscriptions
        SET cycle_months = 3,
            unit_price_cents = GREATEST(
                300,
                LEAST(
                    370,
                    ROUND(
                        amount_cents::numeric / GREATEST(tickets_per_month * 3, 1)
                    )::int
                )
            ),
            installments = 1,
            refund_window_ends_at = paid_at + interval '7 days'
        """
    )
    op.alter_column("pass_subscriptions", "cycle_months", nullable=False)
    op.alter_column("pass_subscriptions", "unit_price_cents", nullable=False)
    op.alter_column("pass_subscriptions", "installments", nullable=False)
    op.alter_column(
        "pass_subscriptions",
        "plan_code",
        type_=sa.String(length=24),
        existing_type=sa.String(length=20),
    )
    op.alter_column(
        "pass_subscriptions",
        "status",
        type_=sa.String(length=16),
        existing_type=sa.String(length=12),
    )

    op.drop_constraint("status_valid", "pass_subscriptions", type_="check")
    op.create_check_constraint(
        "status_valid",
        "pass_subscriptions",
        "status IN ('pending', 'scheduled', 'active', 'expired', "
        "'cancelled', 'refunded', 'payment_failed')",
    )
    op.create_check_constraint(
        "cycle_months_valid",
        "pass_subscriptions",
        "cycle_months IN (1, 3, 6)",
    )
    op.create_check_constraint(
        "unit_price_range",
        "pass_subscriptions",
        "unit_price_cents BETWEEN 300 AND 370",
    )
    op.create_check_constraint("installments_valid", "pass_subscriptions", "installments = 1")
    op.create_index(
        "ix_pass_subscriptions_user_status",
        "pass_subscriptions",
        ["user_id", "status"],
    )

    # --- ciclos ----------------------------------------------------------
    op.add_column(
        "pass_deliveries",
        sa.Column("period", sa.String(length=7), nullable=True),
    )
    op.add_column(
        "pass_deliveries",
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pass_deliveries",
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pass_deliveries",
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'delivered'"), nullable=True
        ),
    )
    op.add_column(
        "pass_deliveries",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        WITH base AS (
            SELECT d.id,
                   COALESCE(s.starts_at, d.delivered_at) AS origin,
                   d.month_index
            FROM pass_deliveries d
            JOIN pass_subscriptions s ON s.id = d.subscription_id
        )
        UPDATE pass_deliveries d
        SET starts_at = b.origin + (((b.month_index - 1) || ' months')::interval),
            ends_at = b.origin + ((b.month_index || ' months')::interval),
            period = to_char(
                b.origin + (((b.month_index - 1) || ' months')::interval),
                'YYYY-MM'
            )
        FROM base b
        WHERE d.id = b.id
        """
    )
    op.execute(
        """
        UPDATE pass_deliveries
        SET status = CASE WHEN ends_at <= now() THEN 'closed' ELSE 'delivered' END,
            closed_at = CASE WHEN ends_at <= now() THEN ends_at ELSE NULL END
        """
    )

    op.alter_column("pass_deliveries", "delivered_at", nullable=True)
    op.alter_column("pass_deliveries", "period", nullable=False)
    op.alter_column("pass_deliveries", "starts_at", nullable=False)
    op.alter_column("pass_deliveries", "ends_at", nullable=False)
    op.alter_column("pass_deliveries", "status", nullable=False)

    op.drop_constraint("month_index_valid", "pass_deliveries", type_="check")
    op.create_check_constraint(
        "month_index_valid", "pass_deliveries", "month_index BETWEEN 1 AND 6"
    )
    op.create_check_constraint(
        "status_valid",
        "pass_deliveries",
        "status IN ('scheduled', 'delivered', 'closed', 'cancelled')",
    )
    op.create_check_constraint("time_order_valid", "pass_deliveries", "ends_at > starts_at")
    op.create_unique_constraint(
        "uq_pass_deliveries_subscription_period",
        "pass_deliveries",
        ["subscription_id", "period"],
    )
    op.create_index("ix_pass_deliveries_status_ends", "pass_deliveries", ["status", "ends_at"])

    # --- fim da venda avulsa (legado permanece) --------------------------
    op.execute("UPDATE ticket_packs SET active = false")


def downgrade() -> None:
    op.execute("UPDATE ticket_packs SET active = true")

    op.drop_index("ix_pass_deliveries_status_ends", table_name="pass_deliveries")
    op.drop_constraint("uq_pass_deliveries_subscription_period", "pass_deliveries", type_="unique")
    op.drop_constraint("time_order_valid", "pass_deliveries", type_="check")
    op.drop_constraint("status_valid", "pass_deliveries", type_="check")
    op.drop_constraint("month_index_valid", "pass_deliveries", type_="check")

    # O schema anterior só representa três meses; ciclos futuros de 6 meses não
    # têm representação e são removidos no downgrade.
    op.execute("DELETE FROM pass_deliveries WHERE month_index > 3")
    op.execute("UPDATE pass_deliveries SET delivered_at = COALESCE(delivered_at, starts_at)")
    op.alter_column("pass_deliveries", "delivered_at", nullable=False)
    op.create_check_constraint(
        "month_index_valid", "pass_deliveries", "month_index BETWEEN 1 AND 3"
    )

    op.drop_column("pass_deliveries", "closed_at")
    op.drop_column("pass_deliveries", "status")
    op.drop_column("pass_deliveries", "ends_at")
    op.drop_column("pass_deliveries", "starts_at")
    op.drop_column("pass_deliveries", "period")

    op.drop_index("ix_pass_subscriptions_user_status", table_name="pass_subscriptions")
    op.drop_constraint("installments_valid", "pass_subscriptions", type_="check")
    op.drop_constraint("unit_price_range", "pass_subscriptions", type_="check")
    op.drop_constraint("cycle_months_valid", "pass_subscriptions", type_="check")
    op.drop_constraint("status_valid", "pass_subscriptions", type_="check")
    op.execute(
        "UPDATE pass_subscriptions SET status = 'cancelled' "
        "WHERE status IN ('scheduled', 'refunded', 'payment_failed')"
    )
    op.alter_column(
        "pass_subscriptions",
        "status",
        type_=sa.String(length=12),
        existing_type=sa.String(length=16),
    )
    op.alter_column(
        "pass_subscriptions",
        "plan_code",
        type_=sa.String(length=20),
        existing_type=sa.String(length=24),
    )
    op.create_check_constraint(
        "status_valid",
        "pass_subscriptions",
        "status IN ('pending', 'active', 'expired', 'cancelled')",
    )
    op.drop_column("pass_subscriptions", "refund_window_ends_at")
    op.drop_column("pass_subscriptions", "refunded_at")
    op.drop_column("pass_subscriptions", "cancel_reason")
    op.drop_column("pass_subscriptions", "cancelled_at")
    op.drop_column("pass_subscriptions", "renewal_of_id")
    op.drop_column("pass_subscriptions", "installments")
    op.drop_column("pass_subscriptions", "unit_price_cents")
    op.drop_column("pass_subscriptions", "cycle_months")

    op.drop_index("ix_pass_plans_active_size", table_name="pass_plans")
    op.drop_table("pass_plans")
