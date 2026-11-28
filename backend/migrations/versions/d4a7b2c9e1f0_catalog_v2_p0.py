"""catálogo v2: planos mensais e passe de temporada separado

Revision ID: d4a7b2c9e1f0
Revises: bc23de45fa67
Create Date: 2026-11-28 00:00:00.000000

Aditiva e reversível. Cria o catálogo da ADR 0079 sem tocar em ``pass_plans``,
``pass_subscriptions``, ``pass_deliveries`` ou ``ticket_packs``: o piloto e o
legado continuam exatamente como estão. A flag ``JOGA_CATALOG_V2_ENABLED``
nasce desligada no código; este schema não é vendável por si só.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7b2c9e1f0"
down_revision: str | Sequence[str] | None = "bc23de45fa67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATALOG_VERSION = 2
CATALOG_NAMESPACE = uuid.UUID("a6d5f1e2-7b3c-4f8a-9d10-5e6f7a8b9c0d")

PRODUCTS: tuple[tuple[str, str, str, int, int | None, int | None], ...] = (
    ("assinatura_mensal_20", "subscription", "Assinatura mensal 20", 1, 20, None),
    ("assinatura_mensal_40", "subscription", "Assinatura mensal 40", 1, 40, None),
    ("assinatura_mensal_70", "subscription", "Assinatura mensal 70", 1, 70, None),
    ("passe_temporada", "season_pass", "Passe de temporada", 3, None, 6),
)

ENTITLEMENTS: dict[str, tuple[str, ...]] = {
    "assinatura_mensal_20": ("tickets",),
    "assinatura_mensal_40": ("tickets",),
    "assinatura_mensal_70": ("tickets",),
    "passe_temporada": (
        "tickets",
        "season_track",
        "cosmetics",
        "advanced_stats",
        "private_lobby",
        "cep_search",
    ),
}

# (produto, meio, parcelas, centavos). Tabela da ADR 0079 §1 e §2:
# assinatura 68/128/217 Pix e 72/135,60/230,30 cartão 1x;
# passe 42,50 Pix, 44,97 cartão 1x e 46,99 cartão 3x.
PRICES: tuple[tuple[str, str, int, int], ...] = (
    ("assinatura_mensal_20", "pix", 1, 6_800),
    ("assinatura_mensal_20", "card", 1, 7_200),
    ("assinatura_mensal_40", "pix", 1, 12_800),
    ("assinatura_mensal_40", "card", 1, 13_560),
    ("assinatura_mensal_70", "pix", 1, 21_700),
    ("assinatura_mensal_70", "card", 1, 23_030),
    ("passe_temporada", "pix", 1, 4_250),
    ("passe_temporada", "card", 1, 4_497),
    ("passe_temporada", "card", 3, 4_699),
)


def _product_id(code: str) -> uuid.UUID:
    return uuid.uuid5(CATALOG_NAMESPACE, f"product:{code}")


def upgrade() -> None:
    op.create_table(
        "catalog_v2_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("months", sa.SmallInteger(), nullable=False),
        sa.Column("tickets_per_month", sa.Integer(), nullable=True),
        sa.Column("tickets_included", sa.Integer(), nullable=True),
        sa.Column(
            "catalog_version",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('subscription', 'season_pass')", name="kind_valid"),
        sa.CheckConstraint("months IN (1, 3)", name="months_valid"),
        sa.CheckConstraint(
            "kind <> 'subscription' OR (months = 1 AND tickets_per_month > 0)",
            name="subscription_valid",
        ),
        sa.CheckConstraint(
            "kind <> 'season_pass' OR (months = 3 AND tickets_included >= 0)",
            name="season_pass_valid",
        ),
        sa.CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_catalog_v2_products_code"),
    )
    op.create_index(
        "ix_catalog_v2_products_active_kind",
        "catalog_v2_products",
        ["active", "kind"],
    )

    op.create_table(
        "catalog_v2_product_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_key", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entitlement_key IN ('tickets', 'season_track', 'cosmetics', "
            "'advanced_stats', 'private_lobby', 'cep_search')",
            name="entitlement_key_valid",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_v2_products.id"],
            name="fk_catalog_v2_product_entitlements_product_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "entitlement_key",
            name="uq_catalog_v2_product_entitlements_product_key",
        ),
    )
    op.create_index(
        "ix_catalog_v2_product_entitlements_product",
        "catalog_v2_product_entitlements",
        ["product_id"],
    )

    op.create_table(
        "catalog_v2_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("payment_method", sa.String(length=8), nullable=False),
        sa.Column("installments", sa.SmallInteger(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        sa.CheckConstraint("installments IN (1, 3)", name="installments_valid"),
        sa.CheckConstraint(
            "payment_method <> 'pix' OR installments = 1",
            name="pix_single_installment",
        ),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_v2_products.id"],
            name="fk_catalog_v2_prices_product_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "payment_method",
            "installments",
            "catalog_version",
            name="uq_catalog_v2_prices_version",
        ),
    )
    op.create_index(
        "ix_catalog_v2_prices_product_method",
        "catalog_v2_prices",
        ["product_id", "payment_method"],
    )

    op.create_table(
        "catalog_v2_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("tickets_per_month", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=8), nullable=False),
        sa.Column("installments", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column(
            "price_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_window_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'past_due', 'cancelled', 'expired', 'refunded')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        sa.CheckConstraint("installments = 1", name="subscription_single_installment"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_catalog_v2_subscriptions_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_v2_products.id"],
            name="fk_catalog_v2_subscriptions_product_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_catalog_v2_subscriptions_user_active",
        "catalog_v2_subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_catalog_v2_subscriptions_user_created",
        "catalog_v2_subscriptions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_catalog_v2_subscriptions_status_ends",
        "catalog_v2_subscriptions",
        ["status", "ends_at"],
    )
    op.create_index(
        "ix_catalog_v2_subscriptions_user_status",
        "catalog_v2_subscriptions",
        ["user_id", "status"],
    )

    op.create_table(
        "catalog_v2_subscription_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("month_index", sa.SmallInteger(), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("month_index BETWEEN 1 AND 3", name="month_index_valid"),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'delivered', 'closed', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["catalog_v2_subscriptions.id"],
            name="fk_catalog_v2_subscription_cycles_subscription_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "month_index",
            name="uq_catalog_v2_subscription_cycles_month",
        ),
        sa.UniqueConstraint(
            "subscription_id",
            "period",
            name="uq_catalog_v2_subscription_cycles_period",
        ),
    )
    op.create_index(
        "ix_catalog_v2_subscription_cycles_status_ends",
        "catalog_v2_subscription_cycles",
        ["status", "ends_at"],
    )

    op.create_table(
        "catalog_v2_season_passes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=8), nullable=False),
        sa.Column("installments", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column(
            "price_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "tickets_granted",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "tickets_redeemed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'cancelled', 'refunded')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        sa.CheckConstraint("installments IN (1, 3)", name="installments_valid"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        sa.CheckConstraint("tickets_granted >= 0", name="tickets_granted_non_negative"),
        sa.CheckConstraint(
            "tickets_redeemed >= 0 AND tickets_redeemed <= tickets_granted",
            name="tickets_redeemed_valid",
        ),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_catalog_v2_season_passes_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_v2_products.id"],
            name="fk_catalog_v2_season_passes_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name="fk_catalog_v2_season_passes_season_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_catalog_v2_season_passes_user_active",
        "catalog_v2_season_passes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_catalog_v2_season_passes_user_created",
        "catalog_v2_season_passes",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_catalog_v2_season_passes_status_ends",
        "catalog_v2_season_passes",
        ["status", "ends_at"],
    )
    op.create_index(
        "ix_catalog_v2_season_passes_user_status",
        "catalog_v2_season_passes",
        ["user_id", "status"],
    )

    op.create_table(
        "catalog_v2_season_pass_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("season_pass_id", sa.Uuid(), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'delivered', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("expires_at > granted_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["season_pass_id"],
            ["catalog_v2_season_passes.id"],
            name="fk_catalog_v2_season_pass_deliveries_pass_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_pass_id",
            name="uq_catalog_v2_season_pass_deliveries_pass",
        ),
    )
    op.create_index(
        "ix_catalog_v2_season_pass_deliveries_status_expires",
        "catalog_v2_season_pass_deliveries",
        ["status", "expires_at"],
    )

    products_table = sa.table(
        "catalog_v2_products",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("label", sa.String()),
        sa.column("months", sa.SmallInteger()),
        sa.column("tickets_per_month", sa.Integer()),
        sa.column("tickets_included", sa.Integer()),
        sa.column("catalog_version", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        products_table,
        [
            {
                "id": _product_id(code),
                "code": code,
                "kind": kind,
                "label": label,
                "months": months,
                "tickets_per_month": tickets_per_month,
                "tickets_included": tickets_included,
                "catalog_version": CATALOG_VERSION,
                "active": True,
            }
            for code, kind, label, months, tickets_per_month, tickets_included in PRODUCTS
        ],
    )

    entitlements_table = sa.table(
        "catalog_v2_product_entitlements",
        sa.column("id", sa.Uuid()),
        sa.column("product_id", sa.Uuid()),
        sa.column("entitlement_key", sa.String()),
    )
    op.bulk_insert(
        entitlements_table,
        [
            {
                "id": uuid.uuid5(
                    CATALOG_NAMESPACE,
                    f"entitlement:{code}:{key}",
                ),
                "product_id": _product_id(code),
                "entitlement_key": key,
            }
            for code, keys in ENTITLEMENTS.items()
            for key in keys
        ],
    )

    prices_table = sa.table(
        "catalog_v2_prices",
        sa.column("id", sa.Uuid()),
        sa.column("product_id", sa.Uuid()),
        sa.column("payment_method", sa.String()),
        sa.column("installments", sa.SmallInteger()),
        sa.column("amount_cents", sa.Integer()),
        sa.column("catalog_version", sa.Integer()),
    )
    op.bulk_insert(
        prices_table,
        [
            {
                "id": uuid.uuid5(
                    CATALOG_NAMESPACE,
                    f"price:{code}:{method}:{installments}:{CATALOG_VERSION}",
                ),
                "product_id": _product_id(code),
                "payment_method": method,
                "installments": installments,
                "amount_cents": amount_cents,
                "catalog_version": CATALOG_VERSION,
            }
            for code, method, installments, amount_cents in PRICES
        ],
    )


def downgrade() -> None:
    # Só remove o que esta revisão criou. O catálogo do piloto e o legado ficam.
    op.drop_table("catalog_v2_season_pass_deliveries")
    op.drop_table("catalog_v2_season_passes")
    op.drop_table("catalog_v2_subscription_cycles")
    op.drop_table("catalog_v2_subscriptions")
    op.drop_table("catalog_v2_prices")
    op.drop_table("catalog_v2_product_entitlements")
    op.drop_table("catalog_v2_products")
