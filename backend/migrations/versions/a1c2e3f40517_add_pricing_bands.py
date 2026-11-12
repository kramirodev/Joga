"""add pricing bands and venue band snapshot

Revision ID: a1c2e3f40517
Revises: b2c3d4e5f6a1
Create Date: 2026-11-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c2e3f40517"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BANDS = (
    ("economica_dia", "Econômica dia", 12_000),
    ("economica_noite", "Econômica noite", 15_000),
    ("padrao_dia", "Padrão dia", 18_000),
    ("padrao_noite", "Padrão noite", 22_000),
    ("coberta", "Coberta", 26_000),
    ("premium", "Premium", 30_000),
)


def upgrade() -> None:
    """Cria o catálogo de faixas e o vínculo com a agenda."""
    op.create_table(
        "pricing_bands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("max_price_cents", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_price_cents > 0", name="max_price_positive"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_pricing_bands_code_version"),
    )
    op.create_index(
        "ix_pricing_bands_active_ceiling",
        "pricing_bands",
        ["active", "max_price_cents"],
    )

    bands_table = sa.table(
        "pricing_bands",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("max_price_cents", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        bands_table,
        [
            {
                "id": f"00000000-0000-4000-8000-00000000000{i}",
                "code": code,
                "label": label,
                "max_price_cents": ceiling,
                "version": 1,
                "active": True,
            }
            for i, (code, label, ceiling) in enumerate(BANDS, start=1)
        ],
    )

    op.add_column(
        "venue_spaces",
        sa.Column(
            "is_covered",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("venue_availability", sa.Column("band_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_venue_availability_band_id",
        "venue_availability",
        "pricing_bands",
        ["band_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_venue_availability_band_id", "venue_availability", ["band_id"])

    # Preenche a faixa das janelas já cadastradas pela menor faixa que cobre o preço.
    op.execute(
        sa.text(
            """
            UPDATE venue_availability AS va
            SET band_id = (
                SELECT pb.id
                FROM pricing_bands AS pb
                WHERE pb.active
                  AND pb.max_price_cents >= va.price_cents
                ORDER BY pb.max_price_cents ASC
                LIMIT 1
            )
            WHERE va.band_id IS NULL
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_venue_availability_band_id", table_name="venue_availability")
    op.drop_constraint(
        "fk_venue_availability_band_id", "venue_availability", type_="foreignkey"
    )
    op.drop_column("venue_availability", "band_id")
    op.drop_column("venue_spaces", "is_covered")
    op.drop_index("ix_pricing_bands_active_ceiling", table_name="pricing_bands")
    op.drop_table("pricing_bands")
