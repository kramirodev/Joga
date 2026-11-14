"""add moderation reports and actions

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-14 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "moderation_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("classifier_version", sa.String(length=40), nullable=False),
        sa.Column("classifier_signals", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "category IN ('HARASSMENT','HATE','THREAT','SEXUAL','SPAM','OTHER')",
            name="category_valid",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED','APPEALED')",
            name="status_valid",
        ),
        sa.CheckConstraint("severity IN ('LOW','MEDIUM','HIGH')", name="severity_valid"),
        sa.CheckConstraint("priority BETWEEN 0 AND 100", name="priority_valid"),
        sa.CheckConstraint(
            "length(description) BETWEEN 1 AND 2000",
            name="description_length_valid",
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lobby_id"], ["lobbies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_moderation_reports_target_created",
        "moderation_reports",
        ["target_user_id", "created_at"],
    )
    op.create_index(
        "ix_moderation_reports_status_priority",
        "moderation_reports",
        ["status", "priority"],
    )
    op.create_index(
        "ix_moderation_reports_reporter_created",
        "moderation_reports",
        ["reporter_id", "created_at"],
    )

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("operator", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("action_type IN ('WARNING','RESTRICT_RANKED')", name="type_valid"),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED','EXPIRED')", name="status_valid"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["report_id"], ["moderation_reports.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_moderation_actions_target_status",
        "moderation_actions",
        ["target_user_id", "status"],
    )
    op.create_index("ix_moderation_actions_report", "moderation_actions", ["report_id"])

    op.create_table(
        "moderation_appeals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=120), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('OPEN','ACCEPTED','REJECTED')", name="status_valid"),
        sa.ForeignKeyConstraint(
            ["action_id"], ["moderation_actions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "action_id", "user_id", name="uq_moderation_appeals_action_user"
        ),
    )


def downgrade() -> None:
    op.drop_table("moderation_appeals")
    op.drop_index("ix_moderation_actions_report", table_name="moderation_actions")
    op.drop_index("ix_moderation_actions_target_status", table_name="moderation_actions")
    op.drop_table("moderation_actions")
    op.drop_index(
        "ix_moderation_reports_reporter_created", table_name="moderation_reports"
    )
    op.drop_index(
        "ix_moderation_reports_status_priority", table_name="moderation_reports"
    )
    op.drop_index(
        "ix_moderation_reports_target_created", table_name="moderation_reports"
    )
    op.drop_table("moderation_reports")
