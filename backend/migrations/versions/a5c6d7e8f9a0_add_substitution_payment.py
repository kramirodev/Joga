"""add substitute payment to booking substitutions

Revision ID: a5c6d7e8f9a0
Revises: f4b5c6d7e8f9
Create Date: 2026-11-09 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "f4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "booking_substitutions",
        sa.Column("substitute_payment_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_booking_substitutions_substitute_payment_id_booking_payments"),
        "booking_substitutions",
        "booking_payments",
        ["substitute_payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        "status IN ('OPEN', 'AWAITING_PAYMENT', 'FILLED', 'EXPIRED', 'CANCELLED')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        "status IN ('OPEN', 'FILLED', 'EXPIRED', 'CANCELLED')",
    )
    op.drop_constraint(
        op.f("fk_booking_substitutions_substitute_payment_id_booking_payments"),
        "booking_substitutions",
        type_="foreignkey",
    )
    op.drop_column("booking_substitutions", "substitute_payment_id")
