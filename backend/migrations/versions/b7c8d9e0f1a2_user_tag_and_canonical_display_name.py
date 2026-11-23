"""tag pública do jogador e nome canônico em maiúsculas

Revision ID: b7c8d9e0f1a2
Revises: 9d3e4f5a6b7c
Create Date: 2026-11-23 15:30:00.000000

O jogador passa a ter uma tag pública estável e única, derivada do UUID:
``#`` + os 8 primeiros hexadecimais maiúsculos (``#9F55A2C1``). Quando duas
contas compartilham esse prefixo, a posterior estende deterministicamente para
10 e depois 12 hexadecimais, na mesma ordem de ``created_at``/``id`` usada pelo
backfill. Um índice único é a autoridade final da unicidade.

``user_profiles.display_name`` é canonizado com ``trim``, espaços repetidos
colapsados e ``upper`` (acentos e Unicode preservados), limitado a 60
caracteres — o mesmo tamanho da coluna. Nome pode repetir: a tag desambigua.
Valores ``NULL`` permanecem ``NULL``.

O downgrade remove a tag e seu índice. A canonização do nome não é revertida:
não há como recuperar a caixa original, e baixar a versão não deve devolver
nomes fora do contrato canônico.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "9d3e4f5a6b7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAG_BASE_HEX = 8
TAG_MAX_HEX = 12
TAG_EXTENSION_LENGTHS = (TAG_BASE_HEX, 10, TAG_MAX_HEX)


def _tag(user_id: uuid.UUID, hex_length: int) -> str:
    return f"#{user_id.hex[:hex_length].upper()}"


def _allocate_tag(user_id: uuid.UUID, used: set[str]) -> str:
    for hex_length in TAG_EXTENSION_LENGTHS:
        candidate = _tag(user_id, hex_length)
        if candidate not in used:
            return candidate

    # Caso teórico de colisão nos 12 primeiros hex: anda no espaço de 12 hex.
    seed = int(user_id.hex[:TAG_MAX_HEX], 16)
    for offset in range(1, 4097):
        candidate = f"#{((seed + offset) % (16**TAG_MAX_HEX)):012X}"
        if candidate not in used:
            return candidate
    raise RuntimeError("tag backfill: não foi possível alocar uma tag única")


def upgrade() -> None:
    op.add_column("users", sa.Column("tag", sa.String(length=13), nullable=True))
    _backfill_tags()
    op.alter_column(
        "users",
        "tag",
        existing_type=sa.String(length=13),
        nullable=False,
    )
    op.create_index("uq_users_tag", "users", ["tag"], unique=True)
    _canonicalize_display_names()


def downgrade() -> None:
    op.drop_index("uq_users_tag", table_name="users")
    op.drop_column("users", "tag")


def _backfill_tags() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM users ORDER BY created_at ASC, id ASC")).all()
    used: set[str] = set()
    updates: list[dict[str, object]] = []
    for (raw_user_id,) in rows:
        user_id = uuid.UUID(str(raw_user_id))
        tag = _allocate_tag(user_id, used)
        used.add(tag)
        updates.append({"user_id": user_id, "tag": tag})
    if updates:
        connection.execute(
            sa.text("UPDATE users SET tag = :tag WHERE id = :user_id"),
            updates,
        )


def _canonicalize_display_names() -> None:
    """Aplica a mesma regra de ``app.core.text.normalize_display_name``.

    A canonização é feita em Python, e não com ``upper()`` do SQL: bancos com
    colação ``C`` deixam ``ã`` minúsculo intacto, enquanto o contrato do
    produto exige acentos maiúsculos.
    """

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT user_id, display_name FROM user_profiles WHERE display_name IS NOT NULL")
    ).all()
    updates: list[dict[str, object]] = []
    for raw_user_id, display_name in rows:
        cleaned = re.sub(r"\s+", " ", str(display_name).strip())
        canonical = cleaned.upper()[:60].rstrip() or None
        if canonical != display_name:
            updates.append({"user_id": raw_user_id, "display_name": canonical})
    if updates:
        connection.execute(
            sa.text(
                "UPDATE user_profiles SET display_name = :display_name WHERE user_id = :user_id"
            ),
            updates,
        )
