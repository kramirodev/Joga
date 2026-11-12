"""Progresso de temporada, trilha e insígnias (ADR 0043)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.season.models import Badge, Season, SeasonItem, SeasonTrackLevel
from app.modules.season.service import (
    MAX_LEVEL,
    ClaimError,
    SeasonNotFound,
    active_season,
    claim_level,
    claimed_levels,
    effective_streak,
    equip_badge,
    get_progress,
    level_for,
    list_badges,
    streak_for,
    tier_for,
    track_for,
    xp_for_level,
)

router = APIRouter(prefix="/me/progress", tags=["season"])


class SeasonView(BaseModel):
    code: str
    starts_at: datetime
    ends_at: datetime


class StreakView(BaseModel):
    current: int
    best: int


class ProgressView(BaseModel):
    season: SeasonView
    xp_total: int
    level: int
    tier: str
    next_level_xp: int | None
    streak: StreakView


class TrackLevelView(BaseModel):
    level: int
    xp_required: int
    item_code: str | None
    item_name: str | None
    free_tickets: int
    track: str
    claimed: bool
    available: bool


class TrackView(BaseModel):
    season: SeasonView
    xp_total: int
    level: int
    levels: list[TrackLevelView]


class BadgeView(BaseModel):
    badge_id: UUID
    code: str
    name: str
    kind: str
    equipped_slot: int | None
    awarded_at: datetime


class BadgeListResponse(BaseModel):
    badges: list[BadgeView]


class EquipRequest(BaseModel):
    badge_id: UUID
    slot: int


def _season_view(season: Season) -> SeasonView:
    return SeasonView(
        code=season.code,
        starts_at=season.starts_at,
        ends_at=season.ends_at,
    )


def _require_season(session: Session, now: datetime) -> Season:
    try:
        return active_season(session, now)
    except SeasonNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "season_not_found"},
        ) from None


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, ClaimError):
        code = exc.args[0] if exc.args else "claim_error"
        if code in {"level_not_found", "badge_not_owned"}:
            return HTTPException(status_code=404, detail={"code": code})
        if code == "pass_required":
            return HTTPException(status_code=403, detail={"code": code})
        return HTTPException(status_code=409, detail={"code": code})
    raise exc


@router.get("", response_model=ProgressView)
def read_progress(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ProgressView:
    """XP, nível, tier e streak da temporada ativa. O cliente não escreve nada."""

    now = utcnow()
    season = _require_season(session, now)
    progress = get_progress(session, current.user_id, season)
    xp_total = progress.xp_total if progress else 0
    level = level_for(xp_total)
    record = streak_for(session, current.user_id)

    return ProgressView(
        season=_season_view(season),
        xp_total=xp_total,
        level=level,
        tier=tier_for(level),
        next_level_xp=None if level >= MAX_LEVEL else xp_for_level(level + 1),
        streak=StreakView(
            current=effective_streak(record, now),
            best=record.best_wins,
        ),
    )


@router.get("/track", response_model=TrackView)
def read_track(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> TrackView:
    """Trilha da temporada com estado de cada nível."""

    season = _require_season(session, utcnow())
    progress = get_progress(session, current.user_id, season)
    xp_total = progress.xp_total if progress else 0
    claimed = claimed_levels(session, current.user_id, season)
    items = {
        item.code: item
        for item in session.scalars(
            select(SeasonItem).where(SeasonItem.season_id == season.id)
        ).all()
    }

    levels = []
    for row in track_for(session, season):
        item = items.get(row.item_code) if row.item_code else None
        levels.append(
            TrackLevelView(
                level=row.level,
                xp_required=row.xp_required,
                item_code=row.item_code,
                item_name=item.name if item else None,
                free_tickets=row.free_tickets,
                track=row.track,
                claimed=row.level in claimed,
                available=xp_total >= row.xp_required and row.level not in claimed,
            )
        )

    return TrackView(
        season=_season_view(season),
        xp_total=xp_total,
        level=level_for(xp_total),
        levels=levels,
    )


@router.post("/track/{level}/claim", response_model=TrackLevelView)
def claim_track_level(
    level: int,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> TrackLevelView:
    """Reivindica a recompensa do nível. Idempotente por nível."""

    season = _require_season(session, utcnow())
    try:
        _claim, item_code, free_tickets = claim_level(
            session, user_id=current.user_id, season=season, level=level
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None

    row = session.get(SeasonTrackLevel, (season.id, level))
    item = (
        session.scalars(select(SeasonItem).where(SeasonItem.code == item_code)).first()
        if item_code
        else None
    )
    return TrackLevelView(
        level=level,
        xp_required=row.xp_required if row else 0,
        item_code=item_code,
        item_name=item.name if item else None,
        free_tickets=free_tickets,
        track=row.track if row else "free",
        claimed=True,
        available=False,
    )


@router.get("/badges", response_model=BadgeListResponse)
def read_badges(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BadgeListResponse:
    """Insígnias do jogador. Até três podem ser equipadas no perfil."""

    return BadgeListResponse(
        badges=[
            BadgeView(
                badge_id=badge.id,
                code=badge.code,
                name=badge.name,
                kind=badge.kind,
                equipped_slot=record.equipped_slot,
                awarded_at=record.awarded_at,
            )
            for record, badge in list_badges(session, current.user_id)
        ]
    )


@router.put("/badges/equip", response_model=BadgeView)
def equip_player_badge(
    payload: EquipRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BadgeView:
    """Equipa a insígnia em um dos três espaços do perfil."""

    try:
        record = equip_badge(
            session, user_id=current.user_id, badge_id=payload.badge_id, slot=payload.slot
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None

    badge = session.get(Badge, record.badge_id)
    return BadgeView(
        badge_id=record.badge_id,
        code=badge.code if badge else "",
        name=badge.name if badge else "",
        kind=badge.kind if badge else "",
        equipped_slot=record.equipped_slot,
        awarded_at=record.awarded_at,
    )
