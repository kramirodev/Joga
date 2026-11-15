"""add postal code cache

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-11-15 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d6e7f8a9b0"
down_revision: str | Sequence[str] | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "postal_code_cache",
        sa.Column("cache_key", sa.String(length=120), nullable=False),
        sa.Column("postal_code", sa.String(length=8), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index(
        "ix_postal_code_cache_expires_at",
        "postal_code_cache",
        ["expires_at"],
    )
    op.create_index(
        "ix_postal_code_cache_postal_code",
        "postal_code_cache",
        ["postal_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_postal_code_cache_postal_code", table_name="postal_code_cache")
    op.drop_index("ix_postal_code_cache_expires_at", table_name="postal_code_cache")
    op.drop_table("postal_code_cache")
