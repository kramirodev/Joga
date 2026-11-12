"""add substitute call fields

Revision ID: e9a0b1c2d3e4
Revises: d8f9a0b1c2d3
Create Date: 2026-11-09 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "d8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "booking_substitutions",
        sa.Column("called_user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_booking_substitutions_called_user_id_users"),
        "booking_substitutions",
        "users",
        ["called_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "booking_substitutions",
        sa.Column("call_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_substitutions",
        sa.Column(
            "call_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_booking_substitutions_status_valid"),
        "booking_substitutions",
        "status IN ('OPEN', 'CALLED', 'AWAITING_PAYMENT', 'FILLED', 'EXPIRED', 'CANCELLED')",
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
        "status IN ('OPEN', 'AWAITING_PAYMENT', 'FILLED', 'EXPIRED', 'CANCELLED')",
    )
    op.drop_column("booking_substitutions", "call_attempts")
    op.drop_column("booking_substitutions", "call_deadline_at")
    op.drop_constraint(
        op.f("fk_booking_substitutions_called_user_id_users"),
        "booking_substitutions",
        type_="foreignkey",
    )
    op.drop_column("booking_substitutions", "called_user_id")
