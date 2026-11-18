"""email and password login

Revision ID: y8b9c0d1e2f3
Revises: x7a8b9c0d1e2
Create Date: 2026-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "x7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Senha Argon2id separada, reset e aviso de senha alterada (ADR 0050)."""
    op.create_table(
        "user_passwords",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("compromised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_passwords_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_passwords"),
    )

    op.drop_constraint("purpose_valid", "phone_challenges", type_="check")
    op.create_check_constraint(
        "purpose_valid",
        "phone_challenges",
        "purpose IN ('registration', 'login', 'phone_change', 'recovery', "
        "'email_verification', 'email_login', 'email_change', 'password_reset')",
    )

    op.drop_constraint("kind_valid", "email_deliveries", type_="check")
    op.create_check_constraint(
        "kind_valid",
        "email_deliveries",
        "kind IN ('email_verification', 'email_login', 'email_change_confirm', "
        "'email_change_notice', 'welcome', 'security_alert', "
        "'account_deletion_notice', 'password_reset', 'password_changed')",
    )


def downgrade() -> None:
    """Remove a senha e devolve as finalidades/tipos ao conjunto anterior."""
    op.execute(
        sa.text("UPDATE phone_challenges SET purpose = 'recovery' WHERE purpose = 'password_reset'")
    )
    op.execute(
        sa.text(
            "UPDATE email_deliveries SET kind = 'email_verification' "
            "WHERE kind IN ('password_reset', 'password_changed')"
        )
    )
    op.drop_constraint("kind_valid", "email_deliveries", type_="check")
    op.create_check_constraint(
        "kind_valid",
        "email_deliveries",
        "kind IN ('email_verification', 'email_login', 'email_change_confirm', "
        "'email_change_notice', 'welcome', 'security_alert', "
        "'account_deletion_notice')",
    )

    op.drop_constraint("purpose_valid", "phone_challenges", type_="check")
    op.create_check_constraint(
        "purpose_valid",
        "phone_challenges",
        "purpose IN ('registration', 'login', 'phone_change', 'recovery', "
        "'email_verification', 'email_login', 'email_change')",
    )
    op.drop_table("user_passwords")
