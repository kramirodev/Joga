"""add rate limit counters

Revision ID: f2b5d8e1a7c3
Revises: e1a4c7d9b230
Create Date: 2026-11-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b5d8e1a7c3"
down_revision: str | Sequence[str] | None = "e1a4c7d9b230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria contadores de rate limiting por janela fixa."""
    op.create_table(
        "rate_limit_counters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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
        sa.CheckConstraint("count >= 0", name="count_non_negative"),
        sa.PrimaryKeyConstraint("id", name="pk_rate_limit_counters"),
        sa.UniqueConstraint(
            "scope",
            "key",
            "window_start",
            name="uq_rate_limit_scope_key_window",
        ),
    )
    op.create_index(
        "ix_rate_limit_window_start",
        "rate_limit_counters",
        ["window_start"],
    )


def downgrade() -> None:
    """Remove os contadores de rate limiting."""
    op.drop_index("ix_rate_limit_window_start", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
