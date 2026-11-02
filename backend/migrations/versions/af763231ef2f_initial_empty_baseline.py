"""initial empty baseline

Revision ID: af763231ef2f
Revises:
Create Date: 2026-11-02 12:19:14.228317

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "af763231ef2f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
