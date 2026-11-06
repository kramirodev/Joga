"""Aplicação de limites de requisição com persistência no banco."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.ratelimit.models import RateLimitCounter


class RateLimitExceeded(Exception):
    """Limite da janela atingido."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"aguarde {retry_after_seconds}s antes de tentar novamente")
        self.retry_after_seconds = retry_after_seconds


def window_start_for(moment: datetime, window_seconds: int) -> datetime:
    """Início da janela fixa que contém o instante informado."""
    epoch = int(ensure_utc(moment).timestamp())
    start = epoch - (epoch % window_seconds)
    return datetime.fromtimestamp(start, tz=UTC)


def enforce(
    session: Session,
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int = 60,
    now: datetime | None = None,
) -> None:
    """Incrementa o contador e levanta ``RateLimitExceeded`` se necessário.

    O limite é aplicado por escopo/chave/janela. No PostgreSQL a linha é
    bloqueada antes do incremento; o índice único resolve a criação concorrente
    da mesma janela.
    """
    if limit <= 0:
        raise ValueError("limit deve ser positivo")
    if window_seconds <= 0:
        raise ValueError("window_seconds deve ser positivo")

    moment = ensure_utc(now or utcnow())
    start = window_start_for(moment, window_seconds)
    counter = _locked_counter(session, scope, key, start)

    if counter is None:
        counter = RateLimitCounter(
            scope=scope,
            key=key,
            window_start=start,
            count=0,
            created_at=moment,
            updated_at=moment,
        )
        try:
            with session.begin_nested():
                session.add(counter)
                session.flush()
        except IntegrityError:
            counter = _locked_counter(session, scope, key, start)
            if counter is None:
                raise

    if counter.count >= limit:
        remaining = (start + timedelta(seconds=window_seconds)) - moment
        raise RateLimitExceeded(max(1, math.ceil(remaining.total_seconds())))

    counter.count += 1
    counter.updated_at = moment
    session.flush()


def _locked_counter(
    session: Session,
    scope: str,
    key: str,
    start: datetime,
) -> RateLimitCounter | None:
    return session.scalar(
        select(RateLimitCounter)
        .where(
            RateLimitCounter.scope == scope,
            RateLimitCounter.key == key,
            RateLimitCounter.window_start == start,
        )
        .with_for_update()
    )
