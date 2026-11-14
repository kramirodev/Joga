"""add pass subscription and purchase payments

Revision ID: e4a1c9d7b203
Revises: d9e95b6f7384
Create Date: 2026-11-13 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4a1c9d7b203"
down_revision: str | Sequence[str] | None = "d9e95b6f7384"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Assinatura do passe, franquias mensais e cobrança Pix de compras."""
    op.create_table(
        "pass_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=20), nullable=False),
        sa.Column("tickets_per_month", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("tickets_per_month > 0", name="tickets_positive"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pass_subscriptions_user_created",
        "pass_subscriptions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_pass_subscriptions_status_ends",
        "pass_subscriptions",
        ["status", "ends_at"],
    )
    op.create_index(
        "uq_pass_subscriptions_user_active",
        "pass_subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "pass_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("month_index", sa.Integer(), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("month_index BETWEEN 1 AND 3", name="month_index_valid"),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.ForeignKeyConstraint(["subscription_id"], ["pass_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "month_index",
            name="uq_pass_deliveries_subscription_month",
        ),
    )

    op.create_table(
        "purchase_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=True),
        sa.Column("provider_order_id", sa.String(length=120), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column("provider_status", sa.String(length=40), nullable=True),
        sa.Column("qr_code", sa.String(length=2000), nullable=True),
        sa.Column("qr_code_base64", sa.Text(), nullable=True),
        sa.Column("ticket_url", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('ticket_pack', 'pass')", name="kind_valid"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "reference_id", name="uq_purchase_payments_reference"),
        sa.UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_purchase_payments_provider_order",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_purchase_payments_provider_payment",
        ),
    )
    op.create_index(
        "ix_purchase_payments_user_created",
        "purchase_payments",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_purchase_payments_user_created", table_name="purchase_payments")
    op.drop_table("purchase_payments")
    op.drop_table("pass_deliveries")
    op.drop_index("uq_pass_subscriptions_user_active", table_name="pass_subscriptions")
    op.drop_index("ix_pass_subscriptions_status_ends", table_name="pass_subscriptions")
    op.drop_index("ix_pass_subscriptions_user_created", table_name="pass_subscriptions")
    op.drop_table("pass_subscriptions")
