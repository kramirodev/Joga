"""canonical clan tags with leading '#'

Revision ID: 3b25be23dfba
Revises: c1d2e3f4a5b6
Create Date: 2026-11-20 22:45:30.486825

A tag do clã passa a ser sempre ``#MIOLO``, com miolo ``[A-Z0-9]{2,7}``. A
migração reescreve as tags existentes de forma determinística e idempotente:
limpa caracteres fora de ``[A-Z0-9]``, corta o miolo em 7 e prefixa ``#``. Se
duas tags normalizadas colidirem, a posterior recebe um sufixo numérico,
registrado no log da migração. Para não colidir com a constraint única durante
as trocas, cada tag alterada passa antes por um valor temporário exclusivo.

O downgrade remove o ``#`` e recria a constraint antiga (2 a 8 caracteres),
também resolvendo colisões por sufixo.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "3b25be23dfba"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")


def _core(tag: str, *, max_length: int) -> str:
    """Miolo canônico: A-Z/0-9, no máximo ``max_length``, no mínimo 2."""

    core = re.sub(r"[^A-Z0-9]", "", tag.strip().lstrip("#").strip().upper())
    core = core[:max_length]
    if len(core) < 2:
        core = (core + "00")[:2]
    return core


def _next_tag(core: str, used: set[str], *, prefixed: bool, max_core: int) -> str:
    prefix = "#" if prefixed else ""
    candidate = f"{prefix}{core}"
    if candidate not in used:
        return candidate
    suffix = 2
    while True:
        suffix_text = str(suffix)
        trimmed = core[: max(2, max_core - len(suffix_text))]
        candidate = f"{prefix}{trimmed}{suffix_text}"
        if candidate not in used:
            return candidate
        suffix += 1


def _temporary_tag(used: set[str]) -> str:
    while True:
        candidate = f"~{uuid.uuid4().hex[:7]}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _rewrite_tags(
    connection: Connection,
    *,
    prefixed: bool,
    max_core: int,
) -> None:
    rows = (
        connection.execute(sa.text("SELECT id, tag FROM clans ORDER BY created_at ASC, id ASC"))
        .mappings()
        .all()
    )
    used: set[str] = set()
    assignments: list[tuple[object, str, str]] = []
    for row in rows:
        original = str(row["tag"])
        core = _core(original, max_length=max_core)
        target = _next_tag(core, used, prefixed=prefixed, max_core=max_core)
        used.add(target)
        if target != original:
            assignments.append((row["id"], original, target))

    if not assignments:
        return

    # Valores temporários evitam colisão transitória com a constraint única
    # enquanto as tags trocam de forma (ex.: "ABC" -> "#ABC", "#ABC" -> "#AB2").
    occupied = {str(row["tag"]) for row in rows} | used
    temporary: list[tuple[object, str, str]] = []
    for clan_id, original, target in assignments:
        temp = _temporary_tag(occupied)
        connection.execute(
            sa.text("UPDATE clans SET tag = :tag WHERE id = :id"),
            {"tag": temp, "id": clan_id},
        )
        temporary.append((clan_id, original, target))

    for clan_id, original, target in temporary:
        connection.execute(
            sa.text("UPDATE clans SET tag = :tag WHERE id = :id"),
            {"tag": target, "id": clan_id},
        )
        logger.info("clan tag migrated: %s -> %s (id=%s)", original, target, clan_id)


def upgrade() -> None:
    connection = op.get_bind()
    _rewrite_tags(connection, prefixed=True, max_core=7)
    op.drop_constraint("tag_length_valid", "clans", type_="check")
    op.create_check_constraint(
        "tag_length_valid",
        "clans",
        "length(tag) BETWEEN 3 AND 8 AND substr(tag, 1, 1) = '#'",
    )


def downgrade() -> None:
    connection = op.get_bind()
    op.drop_constraint("tag_length_valid", "clans", type_="check")
    _rewrite_tags(connection, prefixed=False, max_core=8)
    op.create_check_constraint(
        "tag_length_valid",
        "clans",
        "length(tag) BETWEEN 2 AND 8",
    )
