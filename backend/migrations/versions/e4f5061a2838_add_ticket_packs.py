"""add ticket packs and purchases

Revision ID: e4f5061a2838
Revises: d3e4f5061927
Create Date: 2026-11-12 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5061a2838"
down_revision: str | Sequence[str] | None = "d3e4f5061927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKS = (
    ("avulso", "Avulso", 3, 370),
    ("pequeno", "Pequeno", 10, 340),
    ("medio", "Médio", 30, 320),
    ("grande", "Grande", 50, 310),
)


def upgrade() -> None:
    """Cria a escada de preço e a intenção de compra de pacote."""
    op.create_table(
        "ticket_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.CheckConstraint("unit_price_cents > 0", name="unit_price_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    packs_table = sa.table(
        "ticket_packs",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("tickets", sa.Integer()),
        sa.column("unit_price_cents", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        packs_table,
        [
            {
                "id": f"00000000-0000-4000-9000-00000000000{i}",
                "code": code,
                "label": label,
                "tickets": tickets,
                "unit_price_cents": unit_price,
                "active": True,
            }
            for i, (code, label, tickets, unit_price) in enumerate(PACKS, start=1)
        ],
    )

    op.create_table(
        "ticket_purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'paid', 'cancelled')", name="status_valid"),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pack_id"], ["ticket_packs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_purchases_user_created",
        "ticket_purchases",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ticket_purchases_user_created", table_name="ticket_purchases")
    op.drop_table("ticket_purchases")
    op.drop_table("ticket_packs")
