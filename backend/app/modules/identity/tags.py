"""Tag pública do jogador, derivada do UUID e única.

A tag é a forma curta de identificar um jogador sem expor o UUID completo nem
dados pessoais. O formato canônico é ``#`` + 8 hexadecimais maiúsculos
(``#9F55A2C1``) e pode crescer para 10 ou 12 hexadecimais quando os primeiros
8 já estão em uso. A extensão é determinística: o candidato é sempre um prefixo
maior do mesmo UUID, na ordem 8, 10 e 12.

A unicidade é garantida pelo índice único de ``users.tag``. O resgate de
colisão feito aqui consulta os valores já persistidos; num empate concorrente
(duas contas com o mesmo prefixo criadas ao mesmo tempo) o índice do banco
continua sendo a autoridade final.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

TAG_PREFIX = "#"
TAG_BASE_HEX = 8
TAG_MAX_HEX = 12
TAG_MAX_LENGTH = 13
TAG_EXTENSION_LENGTHS = (TAG_BASE_HEX, 10, TAG_MAX_HEX)
TAG_FALLBACK_SCAN_LIMIT = 4096


def tag_from_uuid(user_id: uuid.UUID, hex_length: int = TAG_BASE_HEX) -> str:
    """Prefixo canônico do UUID em hexadecimais maiúsculos, com ``#``."""

    if not TAG_BASE_HEX <= hex_length <= TAG_MAX_HEX:
        raise ValueError("comprimento de tag fora do intervalo permitido")
    return f"{TAG_PREFIX}{user_id.hex[:hex_length].upper()}"


def default_user_tag(context: Any) -> str:
    """Valor padrão de ``User.tag`` para qualquer criação direta do modelo.

    Lê o ``id`` já calculado pelo SQLAlchemy no mesmo INSERT. A resolução de
    colisão fica a cargo de :func:`next_available_tag` nos fluxos de cadastro;
    aqui o prefixo de 8 hex é a base determinística.
    """

    user_id = context.get_current_parameters().get("id")
    if not isinstance(user_id, uuid.UUID):
        raise ValueError("tag do usuário exige id UUID")
    return tag_from_uuid(user_id)


def next_available_tag(session: Session, user_id: uuid.UUID) -> str:
    """Primeira tag livre do UUID, estendendo 8 → 10 → 12 hex se preciso."""

    # Import local para evitar ciclo: o modelo importa este módulo.
    from app.modules.identity.models import User

    for hex_length in TAG_EXTENSION_LENGTHS:
        candidate = tag_from_uuid(user_id, hex_length)
        if session.scalar(select(User.id).where(User.tag == candidate)) is None:
            return candidate

    # Caso teórico: os 12 primeiros hex já pertencem a outra conta. Percorre o
    # espaço de 12 hex de forma determinística, mantendo o comprimento máximo.
    seed = int(user_id.hex[:TAG_MAX_HEX], 16)
    for offset in range(1, TAG_FALLBACK_SCAN_LIMIT + 1):
        candidate = f"{TAG_PREFIX}{((seed + offset) % (16**TAG_MAX_HEX)):012X}"
        if session.scalar(select(User.id).where(User.tag == candidate)) is None:
            return candidate
    raise RuntimeError("não foi possível alocar uma tag única para o usuário")


__all__ = [
    "TAG_BASE_HEX",
    "TAG_EXTENSION_LENGTHS",
    "TAG_MAX_HEX",
    "TAG_MAX_LENGTH",
    "TAG_PREFIX",
    "default_user_tag",
    "next_available_tag",
    "tag_from_uuid",
]
