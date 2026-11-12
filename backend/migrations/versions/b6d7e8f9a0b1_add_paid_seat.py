"""add paid seat substitutions

Revision ID: b6d7e8f9a0b1
Revises: a5c6d7e8f9a0
Create Date: 2026-11-09 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "a5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "booking_substitutions",
        sa.Column("covered_by_payment_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_booking_substitutions_covered_by_payment_id_booking_payments"),
        "booking_substitutions",
        "booking_payments",
        ["covered_by_payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "booking_substitutions",
        sa.Column(
            "paid_seat",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("booking_substitutions", "paid_seat")
    op.drop_constraint(
        op.f("fk_booking_substitutions_covered_by_payment_id_booking_payments"),
        "booking_substitutions",
        type_="foreignkey",
    )
    op.drop_column("booking_substitutions", "covered_by_payment_id")
