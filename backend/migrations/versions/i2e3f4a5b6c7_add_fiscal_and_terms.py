"""add fiscal documents and terms versions

Revision ID: i2e3f4a5b6c7
Revises: h1d2e3f4a5b6
Create Date: 2026-11-16 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "h1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiscal_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("issuer_cnpj", sa.String(length=14), nullable=False),
        sa.Column("taker_user_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending_manual'"),
            nullable=False,
        ),
        sa.Column("number", sa.String(length=60), nullable=True),
        sa.Column("provider_ref", sa.String(length=120), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending_manual', 'issued', 'failed', 'not_required')",
            name="status_valid",
        ),
        sa.CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taker_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", name="uq_fiscal_documents_booking"),
    )
    op.create_index(
        "ix_fiscal_documents_status_created",
        "fiscal_documents",
        ["status", "created_at"],
    )

    op.create_table(
        "terms_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("legal_review_ref", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'approved')", name="status_valid"),
        sa.CheckConstraint(
            "status = 'approved' OR published_at IS NULL",
            name="published_requires_approval",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )


def downgrade() -> None:
    op.drop_table("terms_versions")
    op.drop_index("ix_fiscal_documents_status_created", table_name="fiscal_documents")
    op.drop_table("fiscal_documents")
