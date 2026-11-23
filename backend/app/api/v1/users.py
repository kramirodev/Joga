"""Busca pública de jogador por nome parcial ou tag exata.

O resultado é deliberadamente mínimo: identificador interno, nome canônico,
tag e relação de amizade. E-mail, telefone, CPF, status de conta e localização
nunca saem por esta rota.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.social.service import (
    InvalidPlayerSearch,
    SocialService,
)

router = APIRouter(tags=["users"])

PlayerRelation = Literal["friend", "incoming_request", "outgoing_request", "none"]


class PlayerSearchResult(BaseModel):
    user_id: UUID
    display_name: str | None
    tag: str
    relation: PlayerRelation


class PlayerSearchResponse(BaseModel):
    results: list[PlayerSearchResult]


@router.get("/users/search", response_model=PlayerSearchResponse)
def search_players(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str, Query(min_length=3, max_length=40)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> PlayerSearchResponse:
    """Busca exata por tag (com/sem ``#``) ou nome sem diferenciar caixa."""

    try:
        entries = SocialService(session).search_players(
            current.user_id,
            q,
            limit=limit,
        )
        session.commit()
    except InvalidPlayerSearch:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_search_query"},
        ) from None
    except RateLimitExceeded as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    return PlayerSearchResponse(
        results=[
            PlayerSearchResult(
                user_id=entry.user_id,
                display_name=entry.display_name,
                tag=entry.tag,
                relation=entry.relation,
            )
            for entry in entries
        ]
    )
