"""tema do cartão no perfil do jogador

Revision ID: f4c8a1e6b2d7
Revises: d4a7b2c9e1f0
Create Date: 2026-11-28 00:00:00.000000

Aditiva e reversível. Acrescenta ``user_profiles.theme_id`` (nullable) para o
tema cosmético do cartão de perfil. O valor é uma chave fechada validada na
escrita; o banco garante apenas limite de tamanho e caixa baixa. Não há
backfill: perfis existentes continuam com o tema padrão do aplicativo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c8a1e6b2d7"
down_revision: str | Sequence[str] | None = "d4a7b2c9e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("theme_id", sa.String(length=40), nullable=True),
    )
    op.create_check_constraint(
        "theme_id_valid",
        "user_profiles",
        "theme_id IS NULL OR (length(theme_id) BETWEEN 1 AND 40 AND theme_id = lower(theme_id))",
    )


def downgrade() -> None:
    op.drop_constraint("theme_id_valid", "user_profiles", type_="check")
    op.drop_column("user_profiles", "theme_id")
