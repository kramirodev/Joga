"""Perfil público mínimo e busca de jogador por nome parcial ou tag exata.

O resultado é deliberadamente mínimo: identificador interno, nome canônico,
tag, relação de amizade, clã ativo e o snapshot do cartão (tema, visual,
progresso e insígnias equipadas). E-mail, telefone, CPF, status de conta,
localização e MMR nunca saem por estas rotas.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.clans.service import active_clan_for
from app.modules.identity.models import User
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.profile.card import PublicCard, build_public_card
from app.modules.profile.models import UserProfile
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.social.models import UserBlock
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


class PublicClanView(BaseModel):
    id: UUID
    name: str
    tag: str


class PublicCardVisualView(BaseModel):
    icon_key: str | None
    frame_key: str | None
    accent_key: str | None
    entry_key: str | None
    emote_key: str | None
    badge_key: str | None
    catalog_version: int


class PublicCardBadgeView(BaseModel):
    code: str
    name: str
    kind: str


class PublicCardView(BaseModel):
    theme_id: str | None
    visual: PublicCardVisualView
    tier: str | None
    level: int | None
    qualifier: str | None
    season_label: str
    record: int
    win_streak: int
    badges: list[PublicCardBadgeView]


class PublicPlayerView(BaseModel):
    user_id: UUID
    display_name: str | None
    tag: str
    relation: PlayerRelation
    clan: PublicClanView | None
    card: PublicCardView | None


def _card_view(card: PublicCard) -> PublicCardView:
    return PublicCardView(
        theme_id=card.theme_id,
        visual=PublicCardVisualView(
            icon_key=card.visual.icon_key,
            frame_key=card.visual.frame_key,
            accent_key=card.visual.accent_key,
            entry_key=card.visual.entry_key,
            emote_key=card.visual.emote_key,
            badge_key=card.visual.badge_key,
            catalog_version=card.visual.catalog_version,
        ),
        tier=card.tier,
        level=card.level,
        qualifier=card.qualifier,
        season_label=card.season_label,
        record=card.record,
        win_streak=card.win_streak,
        badges=[
            PublicCardBadgeView(code=badge.code, name=badge.name, kind=badge.kind)
            for badge in card.badges
        ],
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "user_not_found"},
    )


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


@router.get("/users/{user_id}", response_model=PublicPlayerView)
def read_player(
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PublicPlayerView:
    """Perfil público mínimo e cartão; conta inexistente, inativa ou bloqueada é 404."""

    blocked_either_direction = exists().where(
        or_(
            (UserBlock.blocker_id == current.user_id) & (UserBlock.blocked_id == User.id),
            (UserBlock.blocker_id == User.id) & (UserBlock.blocked_id == current.user_id),
        )
    )
    row = session.execute(
        select(User.id, User.tag, UserProfile.display_name, UserProfile.theme_id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(
            User.id == user_id,
            User.status == "active",
            ~blocked_either_direction,
        )
    ).first()
    if row is None:
        raise _not_found()

    relation = SocialService(session).relation_with(current.user_id, user_id)
    clan = active_clan_for(session, user_id)
    card = build_public_card(session, user_id, theme_id=row.theme_id)
    return PublicPlayerView(
        user_id=row.id,
        display_name=row.display_name,
        tag=row.tag,
        relation=relation,
        clan=(
            PublicClanView(id=clan.id, name=clan.name, tag=clan.tag) if clan is not None else None
        ),
        card=_card_view(card),
    )
