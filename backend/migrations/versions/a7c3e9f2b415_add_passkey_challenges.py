"""add passkey challenges

Revision ID: a7c3e9f2b415
Revises: d4a7f2c9e610
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f2b415"
down_revision: str | Sequence[str] | None = "d4a7f2c9e610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria os desafios WebAuthn de uso único."""
    op.create_table(
        "passkey_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("challenge", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('registration', 'authentication')",
            name="purpose_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_passkey_challenges_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_passkey_challenges"),
    )
    op.create_index(
        "ix_passkey_challenges_user_id",
        "passkey_challenges",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_passkey_challenges_user_created",
        "passkey_challenges",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_passkey_challenges_challenge",
        "passkey_challenges",
        ["challenge"],
        unique=True,
    )


def downgrade() -> None:
    """Remove os desafios WebAuthn."""
    op.drop_table("passkey_challenges")
