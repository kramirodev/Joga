"""add pricing band tickets and participant settlement

Revision ID: f5a6172b3949
Revises: e4f5061a2838
Create Date: 2026-11-12 14:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6172b3949"
down_revision: str | Sequence[str] | None = "e4f5061a2838"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MATRIX: dict[str, dict[int, int]] = {
    "economica_dia": {5: 5, 6: 4, 4: 6, 3: 8},
    "economica_noite": {5: 6, 6: 5, 4: 8, 3: 10},
    "padrao_dia": {5: 7, 6: 6, 4: 9, 3: 12},
    "padrao_noite": {5: 9, 6: 7, 4: 11, 3: 14},
    "coberta": {5: 10, 6: 9, 4: 13, 3: 17},
    "premium": {5: 12, 6: 10, 4: 14, 3: 19},
}


def upgrade() -> None:
    """Cria a tabela 2D faixa × formato e o modo de quitação por ingresso."""
    op.create_table(
        "pricing_band_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("band_id", sa.Uuid(), nullable=False),
        sa.Column("team_size", sa.Integer(), nullable=False),
        sa.Column("tickets", sa.Integer(), nullable=False),
        sa.CheckConstraint("team_size > 0", name="team_size_positive"),
        sa.CheckConstraint("tickets > 0", name="tickets_positive"),
        sa.ForeignKeyConstraint(["band_id"], ["pricing_bands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("band_id", "team_size", name="uq_pricing_band_tickets"),
    )

    connection = op.get_bind()
    bands = {
        row[0]: row[1]
        for row in connection.execute(
            sa.text("SELECT code, id FROM pricing_bands WHERE version = 1")
        ).all()
    }
    rows = []
    for code, by_team_size in MATRIX.items():
        band_id = bands.get(code)
        if band_id is None:
            continue
        for team_size, tickets in by_team_size.items():
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "band_id": band_id,
                    "team_size": team_size,
                    "tickets": tickets,
                }
            )
    if rows:
        op.bulk_insert(
            sa.table(
                "pricing_band_tickets",
                sa.column("id", sa.Uuid()),
                sa.column("band_id", sa.Uuid()),
                sa.column("team_size", sa.Integer()),
                sa.column("tickets", sa.Integer()),
            ),
            rows,
        )

    op.add_column(
        "booking_participants",
        sa.Column("settled_with", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "booking_participants",
        sa.Column(
            "tickets_consumed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "settled_with_valid",
        "booking_participants",
        "settled_with IS NULL OR settled_with IN ('pix', 'tickets')",
    )
    op.create_check_constraint(
        "tickets_consumed_non_negative",
        "booking_participants",
        "tickets_consumed >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "tickets_consumed_non_negative", "booking_participants", type_="check"
    )
    op.drop_constraint("settled_with_valid", "booking_participants", type_="check")
    op.drop_column("booking_participants", "tickets_consumed")
    op.drop_column("booking_participants", "settled_with")
    op.drop_table("pricing_band_tickets")
