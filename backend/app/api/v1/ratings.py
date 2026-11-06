"""Endpoints de leitura do rating competitivo e ranking."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.profile.models import SportFormat
from app.modules.ratings.engine import (
    DEFAULT_RATING,
    PLACEMENT_MATCHES,
    division_for,
    division_progress,
)
from app.modules.ratings.models import ALGORITHM_VERSION
from app.modules.ratings.service import RatingService

router = APIRouter(tags=["ratings"])


class MyRatingResponse(BaseModel):
    format_id: UUID
    algorithm_version: str
    division: str
    provisional: bool
    placement_matches_remaining: int
    progress: float | None
    next_division: str | None
    position: int | None
    matches_played: int
    last_rated_at: datetime | None


class RankingEntry(BaseModel):
    position: int
    user_id: UUID
    display_name: str | None
    division: str
    matches_played: int


class RankingResponse(BaseModel):
    format_id: UUID
    algorithm_version: str
    placement_matches: int
    total: int
    limit: int
    offset: int
    entries: list[RankingEntry]


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _format_or_404(session: Session, format_id: UUID) -> SportFormat:
    sport_format = session.get(SportFormat, format_id)
    if sport_format is None or not sport_format.active:
        raise _error("format_not_found", status.HTTP_404_NOT_FOUND)
    return sport_format


@router.get("/ratings/me", response_model=MyRatingResponse)
def get_my_rating(
    format_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MyRatingResponse:
    """Divisão e progresso do usuário, sem expor MMR bruto ou Trust Factor."""
    _format_or_404(session, format_id)
    service = RatingService(session)
    account = service.account_for(current.user_id, format_id)
    if account is None:
        progress_data = division_progress(DEFAULT_RATING, 0)
        return MyRatingResponse(
            format_id=format_id,
            algorithm_version=ALGORITHM_VERSION,
            division=str(progress_data["division"]),
            provisional=True,
            placement_matches_remaining=int(progress_data["placement_matches_remaining"] or 0),
            progress=None,
            next_division=None,
            position=None,
            matches_played=0,
            last_rated_at=None,
        )

    progress_data = division_progress(account.rating, account.matches_played)
    return MyRatingResponse(
        format_id=format_id,
        algorithm_version=account.algorithm_version,
        division=str(progress_data["division"]),
        provisional=bool(progress_data["provisional"]),
        placement_matches_remaining=int(progress_data["placement_matches_remaining"] or 0),
        progress=(
            float(progress_data["progress"]) if progress_data["progress"] is not None else None
        ),
        next_division=(
            str(progress_data["next_division"])
            if progress_data["next_division"] is not None
            else None
        ),
        position=service.position_for(account),
        matches_played=account.matches_played,
        last_rated_at=account.last_rated_at,
    )


@router.get("/rankings", response_model=RankingResponse)
def get_ranking(
    format_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RankingResponse:
    """Top de jogadores colocados por formato, sem MMR bruto."""
    _format_or_404(session, format_id)
    rows, total = RatingService(session).leaderboard(
        format_id,
        limit=limit,
        offset=offset,
    )
    entries = [
        RankingEntry(
            position=offset + index + 1,
            user_id=account.user_id,
            display_name=display_name,
            division=division_for(account.rating, account.matches_played),
            matches_played=account.matches_played,
        )
        for index, (account, display_name) in enumerate(rows)
    ]
    return RankingResponse(
        format_id=format_id,
        algorithm_version=ALGORITHM_VERSION,
        placement_matches=PLACEMENT_MATCHES,
        total=total,
        limit=limit,
        offset=offset,
        entries=entries,
    )
