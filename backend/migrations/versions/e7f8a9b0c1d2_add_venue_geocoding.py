"""add venue postal code and geocoding metadata

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-11-15 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_venues",
        sa.Column("postal_code", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "organization_venues",
        sa.Column("geocoding_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "organization_venues",
        sa.Column("geocoding_precision", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "organization_venues",
        sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "geocoding_precision_valid",
        "organization_venues",
        "geocoding_precision IS NULL "
        "OR geocoding_precision IN ('street', 'venue', 'approximate', 'manual')",
    )
    # Coordenadas já gravadas foram digitadas ou importadas sem proveniência
    # conhecida; marcá-las como manuais evita sugerir precisão que não existe.
    op.execute(
        "UPDATE organization_venues SET geocoding_precision = 'manual' "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint("geocoding_precision_valid", "organization_venues", type_="check")
    op.drop_column("organization_venues", "geocoded_at")
    op.drop_column("organization_venues", "geocoding_precision")
    op.drop_column("organization_venues", "geocoding_source")
    op.drop_column("organization_venues", "postal_code")
