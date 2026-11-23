"""nota de decisão e consulta dos próprios pedidos de clã

Revision ID: 9d3e4f5a6b7c
Revises: 8b2c3d4e5f60
Create Date: 2026-11-23 12:00:00.000000

O jogador precisa acompanhar o próprio pedido de entrada (``GET
/me/clan-requests``) e o admin precisa de uma nota de decisão separada da
mensagem escrita por quem pediu. O índice por jogador cobre a listagem
``pending``/``history``; o índice único parcial de pedidos pendentes existente
não é recriado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d3e4f5a6b7c"
down_revision: str | Sequence[str] | None = "8b2c3d4e5f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clan_join_requests",
        sa.Column("decision_note", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "ix_clan_join_requests_user_status_created",
        "clan_join_requests",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clan_join_requests_user_status_created",
        table_name="clan_join_requests",
    )
    op.drop_column("clan_join_requests", "decision_note")
