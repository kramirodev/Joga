"""Catálogo público de esportes e identidade visual do jogador."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.catalog.sports import list_public_catalog
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.profile.models import Sport, SportFormat
from app.modules.visual.models import VisualCatalogItem
from app.modules.visual.seed import active_items
from app.modules.visual.service import (
    VISUAL_CATALOG_VERSION,
    InvalidVisualItem,
    VisualItemLocked,
    get_identity,
    set_identity,
)

router = APIRouter(tags=["catalog"])

SportCategory = Literal["collective", "individual", "racket", "beach"]


class VisualItemView(BaseModel):
    key: str
    kind: str
    name: str
    asset_ref: str
    season: str | None
    unlock_state: str


class VisualCatalogResponse(BaseModel):
    catalog_version: int
    items: list[VisualItemView]


class VisualIdentityView(BaseModel):
    user_id: UUID
    icon_key: str | None
    frame_key: str | None
    accent_key: str | None
    entry_key: str | None
    emote_key: str | None
    badge_key: str | None
    catalog_version: int


class VisualIdentityUpdate(BaseModel):
    icon_key: str = Field(min_length=2, max_length=64)
    frame_key: str = Field(min_length=2, max_length=64)
    accent_key: str = Field(min_length=2, max_length=64)
    entry_key: str = Field(min_length=2, max_length=64)
    emote_key: str = Field(min_length=2, max_length=64)
    badge_key: str = Field(min_length=2, max_length=64)


class SportFormatView(BaseModel):
    id: UUID
    slug: str
    name: str
    team_size: int
    players_per_team: int
    total_participants: int
    duration_minutes: int
    period_count: int
    score_model: str
    positions: list[str]
    active: bool
    version: int


class SportView(BaseModel):
    id: UUID
    slug: str
    name: str
    category: SportCategory
    icon_key: str
    sort_order: int
    active: bool
    formats: list[SportFormatView]


class PublicSportsCatalogResponse(BaseModel):
    sports: list[SportView]


def _visual_item_view(item: VisualCatalogItem) -> VisualItemView:
    return VisualItemView(
        key=item.key,
        kind=item.kind,
        name=item.name,
        asset_ref=item.asset_ref,
        season=item.season,
        unlock_state=item.unlock_state,
    )


def _identity_view(session: Session, user_id: UUID) -> VisualIdentityView:
    view = get_identity(session, user_id)
    return VisualIdentityView(
        user_id=view.user_id,
        icon_key=view.icon_key,
        frame_key=view.frame_key,
        accent_key=view.accent_key,
        entry_key=view.entry_key,
        emote_key=view.emote_key,
        badge_key=view.badge_key,
        catalog_version=view.catalog_version,
    )


def _format_view(item: SportFormat) -> SportFormatView:
    return SportFormatView(
        id=item.id,
        slug=item.slug,
        name=item.name,
        team_size=item.team_size,
        players_per_team=item.players_per_team,
        total_participants=item.total_participants,
        duration_minutes=item.duration_minutes,
        period_count=item.period_count,
        score_model=item.score_model,
        positions=list(item.positions or []),
        active=item.active,
        version=item.version,
    )


def _sport_view(sport: Sport, formats: list[SportFormat]) -> SportView:
    return SportView(
        id=sport.id,
        slug=sport.slug,
        name=sport.name,
        category=cast(SportCategory, sport.category),
        icon_key=sport.icon_key,
        sort_order=sport.sort_order,
        active=sport.active,
        formats=[_format_view(item) for item in formats],
    )


def _visual_error(exc: Exception) -> HTTPException:
    if isinstance(exc, VisualItemLocked):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "visual_item_locked"},
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "invalid_visual_item"},
    )


@router.get("/catalog/visual", response_model=VisualCatalogResponse)
def read_visual_catalog(
    session: Annotated[Session, Depends(get_session)],
) -> VisualCatalogResponse:
    """Catálogo fechado e público; não expõe escolhas de terceiros."""

    return VisualCatalogResponse(
        catalog_version=VISUAL_CATALOG_VERSION,
        items=[_visual_item_view(item) for item in active_items(session)],
    )


@router.get("/me/visual", response_model=VisualIdentityView)
def read_my_visual_identity(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VisualIdentityView:
    return _identity_view(session, current.user_id)


@router.put("/me/visual", response_model=VisualIdentityView)
def replace_my_visual_identity(
    payload: VisualIdentityUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VisualIdentityView:
    """Substitui os seis slots; chave livre/URL nunca é aceita."""

    try:
        set_identity(
            session,
            current.user_id,
            {
                "icon": payload.icon_key,
                "frame": payload.frame_key,
                "accent": payload.accent_key,
                "entry": payload.entry_key,
                "emote": payload.emote_key,
                "badge": payload.badge_key,
            },
        )
        session.commit()
    except (InvalidVisualItem, VisualItemLocked) as exc:
        session.rollback()
        raise _visual_error(exc) from None
    return _identity_view(session, current.user_id)


@router.get("/catalog/sports", response_model=PublicSportsCatalogResponse)
def read_public_sports_catalog(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(min_length=2, max_length=40)] = None,
    category: Annotated[SportCategory | None, Query()] = None,
) -> PublicSportsCatalogResponse:
    """Somente esportes ativos com ao menos um formato ativo.

    ``q`` busca em nome e slug, sem curingas implícitos; ``category`` filtra
    pelo tipo fechado do esporte.
    """

    if q is not None and len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_query"},
        )
    return PublicSportsCatalogResponse(
        sports=[
            _sport_view(sport, formats)
            for sport, formats in list_public_catalog(session, q=q, category=category)
        ]
    )
