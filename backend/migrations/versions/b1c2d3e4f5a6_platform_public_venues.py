"""quadras públicas da plataforma

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-11-20 00:00:00.000000

Adiciona a organização da plataforma (`joga-publico`), o marcador de quadra
pública e o formato/preço administrativo do espaço.

``venue_spaces.price_cents`` é a fonte de PUBLICAÇÃO; ``venue_availability``
continua sendo a fonte da RESERVA. Em espaço público, os dois valores devem
coincidir, e o serviço mantém as janelas sincronizadas ao editar o espaço.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "a0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_SLUG = "joga-publico"


def upgrade() -> None:
    op.add_column("organizations", sa.Column("slug", sa.String(length=60), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("is_platform", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint("uq_organizations_slug", "organizations", ["slug"])

    op.add_column(
        "organization_venues",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column("venue_spaces", sa.Column("format_id", sa.Uuid(), nullable=True))
    op.add_column("venue_spaces", sa.Column("price_cents", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_venue_spaces_format_id_sport_formats",
        "venue_spaces",
        "sport_formats",
        ["format_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "price_non_negative",
        "venue_spaces",
        "price_cents IS NULL OR price_cents >= 0",
    )
    op.create_index("ix_venue_spaces_format_id", "venue_spaces", ["format_id"])

    organizations = sa.table(
        "organizations",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_platform", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("payout_status", sa.String()),
    )
    op.bulk_insert(
        organizations,
        [
            {
                "id": uuid.uuid4(),
                "slug": PLATFORM_SLUG,
                "name": "JOGA — Quadras Públicas",
                "is_platform": True,
                "status": "active",
                "payout_status": "blocked",
            }
        ],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM organizations WHERE slug = '{PLATFORM_SLUG}'")

    op.drop_index("ix_venue_spaces_format_id", table_name="venue_spaces")
    op.drop_constraint("price_non_negative", "venue_spaces", type_="check")
    op.drop_constraint(
        "fk_venue_spaces_format_id_sport_formats",
        "venue_spaces",
        type_="foreignkey",
    )
    op.drop_column("venue_spaces", "price_cents")
    op.drop_column("venue_spaces", "format_id")

    op.drop_column("organization_venues", "is_public")

    op.drop_constraint("uq_organizations_slug", "organizations", type_="unique")
    op.drop_column("organizations", "is_platform")
    op.drop_column("organizations", "slug")
