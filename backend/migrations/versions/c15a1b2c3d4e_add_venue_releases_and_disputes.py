"""add venue releases and financial disputes

Revision ID: c15a1b2c3d4e
Revises: bb4083b7b697
Create Date: 2026-11-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c15a1b2c3d4e"
down_revision: str | Sequence[str] | None = "bb4083b7b697"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "venue_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
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
            "status IN ('PENDING', 'RELEASED', 'FAILED', 'REVERSED')",
            name=op.f("ck_venue_releases_status_valid"),
        ),
        sa.CheckConstraint(
            "amount_cents >= 0",
            name=op.f("ck_venue_releases_amount_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_venue_releases_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_venue_releases_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venue_releases")),
        sa.UniqueConstraint("booking_id", name="uq_venue_releases_booking"),
    )
    op.create_index(
        "ix_venue_releases_org_status_eligible",
        "venue_releases",
        ["organization_id", "status", "eligible_at"],
        unique=False,
    )

    op.create_table(
        "financial_disputes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=120), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            "status IN ('OPEN', 'ACCEPTED', 'REJECTED', 'WITHDRAWN')",
            name=op.f("ck_financial_disputes_status_valid"),
        ),
        sa.CheckConstraint(
            "amount_cents >= 0",
            name=op.f("ck_financial_disputes_amount_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_financial_disputes_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_financial_disputes_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_financial_disputes_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["venue_releases.id"],
            name=op.f("fk_financial_disputes_release_id_venue_releases"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_disputes")),
    )
    op.create_index(
        "ix_financial_disputes_org_status_created",
        "financial_disputes",
        ["organization_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_financial_disputes_open_booking",
        "financial_disputes",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    # Backfill: liberações simuladas gravadas no ledger pela Fase 14C passam a
    # ter registro próprio, preservando o histórico já validado.
    op.execute(
        """
        INSERT INTO venue_releases (
            id, organization_id, booking_id, amount_cents, status,
            eligible_at, released_at, reason, provider_reference,
            created_at, updated_at
        )
        SELECT DISTINCT ON (b.id)
            gen_random_uuid(), b.organization_id, b.id,
            le.amount_cents, 'RELEASED',
            COALESCE(b.completed_at, le.created_at, now()),
            COALESCE(b.completed_at, le.created_at, now()),
            'backfill_14c', 'simulated:legacy',
            le.created_at, now()
        FROM ledger_entries le
        JOIN bookings b ON b.id = le.booking_id
        WHERE le.entry_type = 'VENUE_RELEASE'
          AND NOT EXISTS (
              SELECT 1 FROM venue_releases vr WHERE vr.booking_id = b.id
          )
        ORDER BY b.id, le.created_at
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_financial_disputes_open_booking", table_name="financial_disputes")
    op.drop_index(
        "ix_financial_disputes_org_status_created",
        table_name="financial_disputes",
    )
    op.drop_table("financial_disputes")
    op.drop_index("ix_venue_releases_org_status_eligible", table_name="venue_releases")
    op.drop_table("venue_releases")
