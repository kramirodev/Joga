"""Ingestão de erros do cliente (Fase 3, ADR 0078).

O painel e o aplicativo móvel enviam lotes pequenos de eventos de erro. O
endpoint é público porque o painel pode falhar antes do login; a identidade
nunca vem do payload — IP, hash e user agent são lidos da requisição. A
gravação passa pelo serviço central de observabilidade, que sanitiza PII e
segredos, e uma falha de log nunca derruba a resposta.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import request_context
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.observability.schemas import (
    ClientEventIn,
    ClientEventsRequest,
    ClientEventsResponse,
)
from app.modules.observability.service import log_event
from app.modules.ratelimit.service import RateLimitExceeded, enforce

logger = logging.getLogger("joga.observability")

router = APIRouter(prefix="/observability", tags=["observability-client"])

CLIENT_EVENTS_SCOPE = "observability_client"

DbSession = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def normalize_screen(value: str | None) -> str | None:
    """Mantém apenas o caminho da tela: sem query string, fragmento nem origem."""
    if not value:
        return None
    path = value.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        return None
    return path


def _details(event: ClientEventIn, screen: str | None) -> dict[str, str | None]:
    return {
        "platform": event.platform,
        "version": event.app_version,
        "screen": screen,
        "build": event.build,
    }


@router.post(
    "/client-events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ClientEventsResponse,
)
def ingest_client_events(
    payload: ClientEventsRequest,
    request: Request,
    session: DbSession,
    settings: SettingsDep,
) -> ClientEventsResponse:
    ip = request_context.request_ip(request)
    ip_hash = request_context.request_ip_hash(request, settings)
    key = ip_hash or ip or "unknown"
    try:
        enforce(
            session,
            scope=CLIENT_EVENTS_SCOPE,
            key=key,
            limit=settings.client_events_rate_limit_per_minute,
            window_seconds=60,
        )
        # O contador é commitado mesmo se a gravação dos eventos falhar.
        session.commit()
    except RateLimitExceeded as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None

    if not settings.observability_enabled:
        return ClientEventsResponse(accepted=0, dropped=0)

    request_id = request_context.current_request_id()
    correlation_id = request_context.current_correlation_id()
    user_agent = request_context.current_user_agent()
    accepted = 0
    dropped = 0
    for event in payload.events:
        screen = normalize_screen(event.screen)
        try:
            log_event(
                event.level,
                "client",
                event.message,
                module=event.module or "client",
                error_code=event.error_code,
                stack=event.stack,
                use_request_context=False,
                request_id=event.request_id or request_id,
                correlation_id=event.correlation_id or correlation_id,
                ip=ip,
                ip_hash=ip_hash,
                user_agent=user_agent,
                # O endpoint da ingestão não é a tela onde o erro ocorreu.
                endpoint=None,
                details=_details(event, screen),
            )
        except Exception as exc:  # noqa: BLE001 - log nunca derruba a resposta
            dropped += 1
            logger.error(
                "falha ao enfileirar evento client error_type=%s",
                type(exc).__name__,
            )
            continue
        accepted += 1
    return ClientEventsResponse(accepted=accepted, dropped=dropped)


__all__ = ["normalize_screen", "router"]
