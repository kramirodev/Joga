"""Estatísticas pessoais, passaporte e inteligência de rede (ADR 0045)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.passes.service import has_active_pass
from app.modules.profile.models import SportFormat
from app.modules.season.models import PlayerBadge, SeasonProgress
from app.modules.season.service import effective_streak, streak_for
from app.modules.stats.service import (
    NETWORK_MIN_SAMPLE,
    NETWORK_WINDOW_DAYS,
    court_history,
    network_cells,
    network_peak_band,
    network_updated_on,
    network_venues,
    own_hours,
    player_totals,
)

router = APIRouter(tags=["stats"])


class TotalsView(BaseModel):
    matches: int
    wins: int
    draws: int
    losses: int
    presence_rate: float | None
    streak_current: int
    streak_best: int


class FormatTotalsView(BaseModel):
    format_id: UUID
    name: str
    matches: int
    wins: int


class StatsView(BaseModel):
    totals: TotalsView
    by_format: list[FormatTotalsView]
    has_pass: bool


class CourtView(BaseModel):
    space_id: UUID
    name: str
    matches: int
    wins: int
    last_played_at: datetime


class CourtListView(BaseModel):
    courts: list[CourtView]


class PassportView(BaseModel):
    totals: TotalsView
    seasons_played: int
    badges: int
    courts: int


class NetworkCellView(BaseModel):
    space_id: UUID
    space_name: str
    band: str
    matches: int
    level: str


class NetworkVenueView(BaseModel):
    space_id: UUID
    name: str
    matches: int
    level: str


class NetworkView(BaseModel):
    updated_on: date
    window_days: int
    min_sample: int
    sample_size: int
    has_pass: bool
    peak_band: str | None
    own_hours: list[str]
    venues: list[NetworkVenueView]
    cells: list[NetworkCellView]


def _require_pass(session: Session, user_id: UUID) -> None:
    if not has_active_pass(session, user_id, utcnow()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "pass_required"},
        )


def _totals_view(
    session: Session,
    user_id: UUID,
    *,
    format_id: UUID | None = None,
) -> TotalsView:
    totals = player_totals(session, user_id, format_id=format_id)
    record = streak_for(session, user_id)
    return TotalsView(
        matches=totals.matches,
        wins=totals.wins,
        draws=totals.draws,
        losses=totals.losses,
        presence_rate=totals.presence_rate,
        streak_current=effective_streak(record, utcnow()),
        streak_best=record.best_wins,
    )


@router.get("/me/stats", response_model=StatsView)
def read_stats(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    format_id: Annotated[UUID | None, Query()] = None,
) -> StatsView:
    """Partidas, resultados e presença. Sem MMR bruto e sem dado de evento."""

    totals = player_totals(session, current.user_id, format_id=format_id)
    format_ids = list(totals.formats.keys())
    names: dict[UUID, str] = {}
    if format_ids:
        names = {
            row[0]: row[1]
            for row in session.execute(
                select(SportFormat.id, SportFormat.name).where(SportFormat.id.in_(format_ids))
            )
        }
    return StatsView(
        totals=_totals_view(session, current.user_id, format_id=format_id),
        by_format=[
            FormatTotalsView(
                format_id=item_id,
                name=names.get(item_id, "Formato"),
                matches=matches,
                wins=totals.wins_by_format.get(item_id, 0),
            )
            for item_id, matches in totals.formats.most_common()
        ],
        has_pass=has_active_pass(session, current.user_id, utcnow()),
    )


@router.get("/me/stats/courts", response_model=CourtListView)
def read_court_history(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> CourtListView:
    """Histórico por quadra. Incluído no passe (ADR 0043 §7)."""

    _require_pass(session, current.user_id)
    return CourtListView(
        courts=[
            CourtView(
                space_id=item.space_id,
                name=item.name,
                matches=item.matches,
                wins=item.wins,
                last_played_at=item.last_played_at,
            )
            for item in court_history(session, current.user_id)
        ]
    )


@router.get("/me/stats/passport", response_model=PassportView)
def read_passport(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PassportView:
    """Resumo de carreira. Incluído no passe; não mostra rating bruto."""

    _require_pass(session, current.user_id)
    seasons = int(
        session.scalar(
            select(func.count(func.distinct(SeasonProgress.season_id))).where(
                SeasonProgress.user_id == current.user_id
            )
        )
        or 0
    )
    badges = int(
        session.scalar(
            select(func.count())
            .select_from(PlayerBadge)
            .where(PlayerBadge.user_id == current.user_id)
        )
        or 0
    )
    return PassportView(
        totals=_totals_view(session, current.user_id),
        seasons_played=seasons,
        badges=badges,
        courts=len(court_history(session, current.user_id)),
    )


@router.get("/me/network", response_model=NetworkView)
def read_network(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> NetworkView:
    """Rede em faixas, diária e com amostra mínima. Nunca tempo real nem filtro."""

    moment = utcnow()
    pass_active = has_active_pass(session, current.user_id, moment)
    venues, sample = network_venues(session, now=moment)
    cells, _ = network_cells(session, now=moment)
    return NetworkView(
        updated_on=network_updated_on(moment),
        window_days=NETWORK_WINDOW_DAYS,
        min_sample=NETWORK_MIN_SAMPLE,
        sample_size=sample,
        has_pass=pass_active,
        peak_band=network_peak_band(session, now=moment),
        own_hours=own_hours(session, current.user_id),
        venues=[
            NetworkVenueView(
                space_id=space_id,
                name=name,
                matches=matches,
                level=level,
            )
            for space_id, name, matches, level in venues
        ],
        cells=(
            [
                NetworkCellView(
                    space_id=cell.space_id,
                    space_name=cell.space_name,
                    band=cell.band,
                    matches=cell.matches,
                    level=cell.level,
                )
                for cell in cells
            ]
            if pass_active
            else []
        ),
    )
