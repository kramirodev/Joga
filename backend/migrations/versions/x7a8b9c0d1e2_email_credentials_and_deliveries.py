"""email credentials and deliveries

Revision ID: x7a8b9c0d1e2
Revises: v6a7b8c9d0e1
Create Date: 2026-11-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "v6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Credencial de e-mail, log de entrega e desafios genéricos (ADR 0050).

    ``phone_challenges`` mantém o nome histórico para não quebrar dados e o
    contrato interno. A partir desta revisão ela armazena desafios de telefone
    e de e-mail, distinguidos por ``subject_type`` e pelo HMAC do sujeito.
    """
    # Nome histórico: `phone_challenges.phone_hash` guarda o HMAC do sujeito
    # (telefone ou e-mail). O rename fica para uma janela futura (PENDENCIAS).
    op.add_column(
        "phone_challenges",
        sa.Column(
            "subject_type",
            sa.String(length=10),
            nullable=False,
            server_default="phone",
        ),
    )
    op.drop_constraint(
        "purpose_valid",
        "phone_challenges",
        type_="check",
    )
    op.create_check_constraint(
        "purpose_valid",
        "phone_challenges",
        "purpose IN ('registration', 'login', 'phone_change', 'recovery', "
        "'email_verification', 'email_login', 'email_change')",
    )
    op.create_check_constraint(
        "subject_type_valid",
        "phone_challenges",
        "subject_type IN ('phone', 'email')",
    )
    op.create_index(
        "ix_phone_challenges_subject_created",
        "phone_challenges",
        ["subject_type", "phone_hash", "created_at"],
        unique=False,
    )

    op.create_table(
        "user_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "hard_bounce_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("undeliverable_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_emails_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_emails"),
    )
    op.create_index("ix_user_emails_user_id", "user_emails", ["user_id"], unique=False)
    op.create_index(
        "uq_user_emails_active_email",
        "user_emails",
        ["email_normalized"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.create_index(
        "uq_user_emails_primary_user",
        "user_emails",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary AND released_at IS NULL"),
    )

    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("last_error_code", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'sent', 'failed', 'bounced')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "kind IN ('email_verification', 'email_login', 'email_change_confirm', "
            "'email_change_notice', 'welcome', 'security_alert', "
            "'account_deletion_notice')",
            name="kind_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="attempts_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_deliveries_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_deliveries"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_email_deliveries_user_id",
        "email_deliveries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_deliveries_user_created",
        "email_deliveries",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_deliveries_kind_created",
        "email_deliveries",
        ["kind", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove a credencial de e-mail e devolve os desafios ao formato original."""
    op.drop_index("ix_email_deliveries_kind_created", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_user_created", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_user_id", table_name="email_deliveries")
    op.drop_table("email_deliveries")

    op.drop_index("uq_user_emails_primary_user", table_name="user_emails")
    op.drop_index("uq_user_emails_active_email", table_name="user_emails")
    op.drop_index("ix_user_emails_user_id", table_name="user_emails")
    op.drop_table("user_emails")

    op.drop_index("ix_phone_challenges_subject_created", table_name="phone_challenges")
    op.drop_constraint(
        "subject_type_valid",
        "phone_challenges",
        type_="check",
    )
    op.drop_constraint(
        "purpose_valid",
        "phone_challenges",
        type_="check",
    )
    op.create_check_constraint(
        "purpose_valid",
        "phone_challenges",
        "purpose IN ('registration', 'login', 'phone_change', 'recovery')",
    )
    op.drop_column("phone_challenges", "subject_type")
