"""add temporary suspension and moderation cooldown support

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-14 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("suspended_until", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("type_valid", "moderation_actions", type_="check")
    op.create_check_constraint(
        "type_valid",
        "moderation_actions",
        "action_type IN ('WARNING','RESTRICT_RANKED','SUSPEND_TEMP')",
    )


def downgrade() -> None:
    op.drop_constraint("type_valid", "moderation_actions", type_="check")
    op.create_check_constraint(
        "type_valid",
        "moderation_actions",
        "action_type IN ('WARNING','RESTRICT_RANKED')",
    )
    op.drop_column("users", "suspended_until")
