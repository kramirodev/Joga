"""Progresso de temporada do jogador (ADR 0043)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.season.service import (
    MAX_LEVEL,
    SeasonNotFound,
    active_season,
    effective_streak,
    get_progress,
    level_for,
    streak_for,
    tier_for,
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


@router.get("", response_model=ProgressView)
def read_progress(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ProgressView:
    """XP, nível, tier e streak da temporada ativa. O cliente não escreve nada."""

    now = utcnow()
    try:
        season = active_season(session, now)
    except SeasonNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "season_not_found"},
        ) from None

    progress = get_progress(session, current.user_id, season)
    xp_total = progress.xp_total if progress else 0
    level = level_for(xp_total)
    record = streak_for(session, current.user_id)
    next_level = None if level >= MAX_LEVEL else xp_for_level(level + 1)

    return ProgressView(
        season=SeasonView(
            code=season.code,
            starts_at=season.starts_at,
            ends_at=season.ends_at,
        ),
        xp_total=xp_total,
        level=level,
        tier=tier_for(level),
        next_level_xp=next_level,
        streak=StreakView(
            current=effective_streak(record, now),
            best=record.best_wins,
        ),
    )
