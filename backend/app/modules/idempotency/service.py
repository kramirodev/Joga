"""Idempotência de POSTs: hash canônico, replay e conflito."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.idempotency.models import IdempotencyRecord


class IdempotencyConflict(Exception):
    """Mesma chave reutilizada com corpo diferente."""


class IdempotencyInProgress(Exception):
    """Requisição concorrente com a mesma chave ainda não concluída."""


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


def payload_hash(payload: Mapping[str, Any]) -> str:
    """Gera hash estável do corpo, independente da ordem das chaves."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find(session: Session, scope: str, key: str) -> IdempotencyRecord | None:
    return session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key == key,
        )
    )


def begin(
    session: Session,
    *,
    scope: str,
    key: str,
    request_hash: str,
) -> StoredResponse | None:
    """Reserva a chave ou devolve a resposta já gravada.

    Retorna ``None`` quando a chave é nova e o chamador deve executar a ação.
    """
    existing = _find(session, scope, key)
    if existing is not None:
        return _resolve(existing, request_hash)

    record = IdempotencyRecord(
        scope=scope,
        key=key,
        request_hash=request_hash,
    )
    try:
        with session.begin_nested():
            session.add(record)
            session.flush()
    except IntegrityError:
        concurrent = _find(session, scope, key)
        if concurrent is None:
            raise
        return _resolve(concurrent, request_hash)
    return None


def finish(
    session: Session,
    *,
    scope: str,
    key: str,
    status_code: int,
    body: dict[str, Any],
) -> None:
    """Grava a resposta de sucesso para replays futuros."""
    record = _find(session, scope, key)
    if record is None:
        raise RuntimeError("registro de idempotência não reservado")
    record.response_status = status_code
    record.response_body = body


def _resolve(record: IdempotencyRecord, request_hash: str) -> StoredResponse:
    if record.request_hash != request_hash:
        raise IdempotencyConflict("mesma chave com corpo diferente")
    if record.response_status is None or record.response_body is None:
        raise IdempotencyInProgress("requisição idempotente ainda em andamento")
    return StoredResponse(status_code=record.response_status, body=record.response_body)
