"""tipo (categoria) do esporte no catálogo

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-11-23 18:00:00.000000

Adiciona ``sports.category`` com os tipos fechados ``collective``,
``individual``, ``racket`` e ``beach``. Nesta rodada cada esporte tem exatamente
um tipo; modalidades híbridas usam o tipo mais específico (o beach tennis fica
em ``racket``, e não em ``beach``).

O backfill é feito por slug. Slugs que não estão no mapeamento — inclusive
esportes criados pelo painel administrativo — permanecem no default
``collective``; a categoria pode ser corrigida depois pelo PATCH do painel.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLLECTIVE_SLUGS = ("futebol", "futsal", "basquete", "handebol", "volei")
RACKET_SLUGS = ("tenis", "padel", "squash", "badminton", "beach-tennis")
INDIVIDUAL_SLUGS = ("corrida", "natacao", "ciclismo", "artes-marciais")
BEACH_SLUGS = ("futevolei", "volei-de-areia")


def _slug_list(slugs: tuple[str, ...]) -> str:
    return ", ".join(f"'{slug}'" for slug in slugs)


def upgrade() -> None:
    op.add_column(
        "sports",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="collective",
        ),
    )
    op.execute(
        f"""
        UPDATE sports SET category = CASE
            WHEN slug IN ({_slug_list(COLLECTIVE_SLUGS)}) THEN 'collective'
            WHEN slug IN ({_slug_list(INDIVIDUAL_SLUGS)}) THEN 'individual'
            WHEN slug IN ({_slug_list(RACKET_SLUGS)}) THEN 'racket'
            WHEN slug IN ({_slug_list(BEACH_SLUGS)}) THEN 'beach'
            ELSE 'collective'
        END
        """
    )
    op.create_check_constraint(
        "category_valid",
        "sports",
        "category IN ('collective', 'individual', 'racket', 'beach')",
    )


def downgrade() -> None:
    op.drop_constraint("category_valid", "sports", type_="check")
    op.drop_column("sports", "category")


__all__ = ["COLLECTIVE_SLUGS", "BEACH_SLUGS", "INDIVIDUAL_SLUGS", "RACKET_SLUGS"]
