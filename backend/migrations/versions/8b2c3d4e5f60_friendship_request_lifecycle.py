"""ciclo de vida de pedidos de amizade

Revision ID: 8b2c3d4e5f60
Revises: 7a1b2c3d4e5f
Create Date: 2026-11-22 12:00:00.000000

Amplia ``friendships`` para pedidos recusados/cancelados, registra o instante
da resposta e garante que ``requested_by`` é sempre um dos participantes.
Os índices parciais de pendentes servem à listagem de recebidos/enviados.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "8b2c3d4e5f60"
down_revision: str | None = "7a1b2c3d4e5f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "friendships",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill defensivo: linhas antigas sempre tiveram requested_by igual a um
    # dos participantes; qualquer anomalia é reparada de forma determinística
    # antes de a constraint entrar em vigor.
    op.execute(
        "UPDATE friendships SET requested_by = user_low_id "
        "WHERE requested_by NOT IN (user_low_id, user_high_id)"
    )

    op.drop_constraint("status_valid", "friendships", type_="check")
    op.create_check_constraint(
        "status_valid",
        "friendships",
        "status IN ('PENDING', 'ACCEPTED', 'REMOVED', 'DECLINED', 'CANCELLED')",
    )
    op.create_check_constraint(
        "requested_by_participant",
        "friendships",
        "requested_by IN (user_low_id, user_high_id)",
    )

    op.create_index(
        "ix_friendship_requested_by_status",
        "friendships",
        ["requested_by", "status"],
    )
    op.create_index(
        "ix_friendship_low_pending_created",
        "friendships",
        ["user_low_id", "created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_friendship_high_pending_created",
        "friendships",
        ["user_high_id", "created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("ix_friendship_high_pending_created", table_name="friendships")
    op.drop_index("ix_friendship_low_pending_created", table_name="friendships")
    op.drop_index("ix_friendship_requested_by_status", table_name="friendships")

    op.drop_constraint("requested_by_participant", "friendships", type_="check")
    op.drop_constraint("status_valid", "friendships", type_="check")
    # O schema antigo não conhece DECLINED/CANCELLED; ambos viram REMOVED.
    op.execute(
        "UPDATE friendships SET status = 'REMOVED' WHERE status IN ('DECLINED', 'CANCELLED')"
    )
    op.create_check_constraint(
        "status_valid",
        "friendships",
        "status IN ('PENDING', 'ACCEPTED', 'REMOVED')",
    )
    op.drop_column("friendships", "responded_at")
