"""add ticket lots and expiry

Revision ID: c9f0a1b2d3e4
Revises: b8e1f2a3c4d5
Create Date: 2026-11-14 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f0a1b2d3e4"
down_revision: str | Sequence[str] | None = "b8e1f2a3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria lotes com validade e o vínculo de consumo por reserva."""
    op.create_table(
        "ticket_lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ref_type", sa.String(length=20), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("ledger_entry_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("original_amount > 0", name="original_amount_positive"),
        sa.CheckConstraint(
            "remaining >= 0 AND remaining <= original_amount",
            name="remaining_valid",
        ),
        sa.CheckConstraint(
            "source IN ('purchase','pass','free_level','admin','refund')",
            name="source_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["ticket_ledger.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ledger_entry_id"),
    )
    op.create_index("ix_ticket_lots_user_expiry", "ticket_lots", ["user_id", "expires_at"])
    op.create_index("ix_ticket_lots_user_source", "ticket_lots", ["user_id", "source"])

    op.create_table(
        "ticket_lot_consumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("ledger_entry_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(["lot_id"], ["ticket_lots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["ticket_ledger.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lot_id",
            "ref_type",
            "ref_id",
            name="uq_ticket_lot_consumption_ref",
        ),
    )
    op.create_index(
        "ix_ticket_lot_consumptions_user_ref",
        "ticket_lot_consumptions",
        ["user_id", "ref_type", "ref_id"],
    )

    op.drop_constraint("source_valid", "ticket_ledger", type_="check")
    op.create_check_constraint(
        "source_valid",
        "ticket_ledger",
        "source IN ('purchase','pass','free_level','consumption','refund','expired','admin')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("source_valid", "ticket_ledger", type_="check")
    op.create_check_constraint(
        "source_valid",
        "ticket_ledger",
        "source IN ('purchase','pass','free_level','consumption','refund','admin')",
    )
    op.drop_index(
        "ix_ticket_lot_consumptions_user_ref",
        table_name="ticket_lot_consumptions",
    )
    op.drop_table("ticket_lot_consumptions")
    op.drop_index("ix_ticket_lots_user_source", table_name="ticket_lots")
    op.drop_index("ix_ticket_lots_user_expiry", table_name="ticket_lots")
    op.drop_table("ticket_lots")
