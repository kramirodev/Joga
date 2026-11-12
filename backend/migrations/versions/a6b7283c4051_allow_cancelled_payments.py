"""allow cancelled booking payments

Revision ID: a6b7283c4051
Revises: f5a6172b3949
Create Date: 2026-11-12 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7283c4051"
down_revision: str | Sequence[str] | None = "f5a6172b3949"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOWED = "'PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED', 'EXPIRED', 'CANCELLED'"
PREVIOUS = "'PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED', 'EXPIRED'"


def upgrade() -> None:
    """Permite encerrar cobranças de quem quitou a vaga com ingressos."""
    op.drop_constraint("status_valid", "booking_payments", type_="check")
    op.create_check_constraint("status_valid", "booking_payments", f"status IN ({ALLOWED})")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            "UPDATE booking_payments SET status = 'EXPIRED' WHERE status = 'CANCELLED'"
        )
    )
    op.drop_constraint("status_valid", "booking_payments", type_="check")
    op.create_check_constraint("status_valid", "booking_payments", f"status IN ({PREVIOUS})")
