"""link organization venue to discovery venue

Revision ID: 0261da35ece5
Revises: 99c1055b81b5
Create Date: 2026-11-07 07:49:41.831208

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0261da35ece5"
down_revision: str | Sequence[str] | None = "99c1055b81b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Vincula o perfil comercial a um local privado do catálogo de descoberta."""
    op.add_column("organization_venues", sa.Column("venue_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        op.f("uq_organization_venues_venue_id"),
        "organization_venues",
        ["venue_id"],
    )
    op.create_foreign_key(
        op.f("fk_organization_venues_venue_id_venues"),
        "organization_venues",
        "venues",
        ["venue_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove o vínculo com o catálogo de descoberta."""
    op.drop_constraint(
        op.f("fk_organization_venues_venue_id_venues"),
        "organization_venues",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_organization_venues_venue_id"),
        "organization_venues",
        type_="unique",
    )
    op.drop_column("organization_venues", "venue_id")
