"""add terms acceptances

Revision ID: r2c3d4e5f6a7
Revises: q1b2c3d4e5f6
Create Date: 2026-11-17 10:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "q1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Prova de aceite (ADR 0049 §9.7). `terms_hash` congela o conteúdo aceito e
    # `ip_hash`/`user_agent_hash` são HMAC/SHA-256, nunca valores em claro.
    op.create_table(
        "terms_acceptances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("terms_version_id", sa.Uuid(), nullable=False),
        sa.Column("context", sa.String(length=20), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("terms_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "context IN ('signup', 'credit_purchase', 'pass_purchase', 'booking_ceiling')",
            name="context_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terms_version_id"], ["terms_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "terms_version_id",
            "context",
            name="uq_terms_acceptances_user_version_context",
        ),
    )
    op.create_index(
        "ix_terms_acceptances_user_accepted",
        "terms_acceptances",
        ["user_id", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_terms_acceptances_user_accepted", table_name="terms_acceptances")
    op.drop_table("terms_acceptances")
