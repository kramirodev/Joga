"""add venue coordinates

Revision ID: d8f9a0b1c2d3
Revises: c7e8f9a0b1c2
Create Date: 2026-11-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = "c7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "organization_venues",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "organization_venues",
        sa.Column("longitude", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_organization_venues_latitude_valid"),
        "organization_venues",
        "latitude IS NULL OR latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        op.f("ck_organization_venues_longitude_valid"),
        "organization_venues",
        "longitude IS NULL OR longitude BETWEEN -180 AND 180",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_organization_venues_longitude_valid"),
        "organization_venues",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_organization_venues_latitude_valid"),
        "organization_venues",
        type_="check",
    )
    op.drop_column("organization_venues", "longitude")
    op.drop_column("organization_venues", "latitude")
