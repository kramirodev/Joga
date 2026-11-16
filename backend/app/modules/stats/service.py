"""Leituras de estatística e rede, sempre a partir do que a plataforma observa.

Regras (ADR 0045):
- estatística fala de partida, presença, resultado, quadra, formato e horário;
- rede é dado agregado, em faixas, com amostra mínima de 20 partidas/30 dias;
- atualização diária, nunca tempo real, e nunca filtro de matchmaking;
- MMR bruto, RD e volatilidade não aparecem.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matchmaking.models import Lobby
from app.modules.venues.models import VenueSpace

NETWORK_WINDOW_DAYS = 30
NETWORK_MIN_SAMPLE = 20
BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 5, "madrugada"),
    (6, 11, "manhã"),
    (12, 17, "tarde"),
    (18, 23, "noite"),
)
LOCAL_ZONE = ZoneInfo("America/Sao_Paulo")


@dataclass
class PlayerTotals:
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    checked_in: int = 0
    no_shows: int = 0
    formats: Counter[uuid.UUID] = field(default_factory=Counter)
    wins_by_format: Counter[uuid.UUID] = field(default_factory=Counter)

    @property
    def presence_rate(self) -> float | None:
        total = self.checked_in + self.no_shows
        if total == 0:
            return None
        return round(self.checked_in / total, 4)


@dataclass
class CourtTotals:
    space_id: uuid.UUID
    name: str
    matches: int
    wins: int
    last_played_at: datetime


@dataclass
class NetworkCell:
    space_id: uuid.UUID
    space_name: str
    band: str
    matches: int
    level: str


def band_for(moment: datetime) -> str:
    hour = ensure_utc(moment).astimezone(LOCAL_ZONE).hour
    for start, end, label in BANDS:
        if start <= hour <= end:
            return label
    return "noite"


def player_totals(
    session: Session,
    user_id: uuid.UUID,
    *,
    format_id: uuid.UUID | None = None,
) -> PlayerTotals:
    statement = (
        select(MatchParticipant, Match, Lobby.format_id)
        .join(Match, Match.id == MatchParticipant.match_id)
        .join(Lobby, Lobby.id == Match.lobby_id)
        .where(
            MatchParticipant.user_id == user_id,
            Match.state == "FINALIZED",
        )
    )
    if format_id is not None:
        statement = statement.where(Lobby.format_id == format_id)

    totals = PlayerTotals()
    for participant, match, played_format in session.execute(statement):
        if participant.status == "no_show":
            totals.no_shows += 1
            continue
        if participant.status != "checked_in":
            continue
        totals.checked_in += 1
        totals.formats[played_format] += 1
        if match.final_result == "DRAW":
            totals.draws += 1
        elif match.final_result == f"TEAM_{participant.team}":
            totals.wins += 1
            totals.wins_by_format[played_format] += 1
        else:
            totals.losses += 1
        totals.matches += 1
    return totals


def court_history(session: Session, user_id: uuid.UUID) -> list[CourtTotals]:
    statement = (
        select(
            VenueSpace.id,
            VenueSpace.name,
            Match.final_result,
            MatchParticipant.team,
            Match.scheduled_start_at,
        )
        .join(Match, Match.id == MatchParticipant.match_id)
        .join(Booking, Booking.lobby_id == Match.lobby_id)
        .join(VenueSpace, VenueSpace.id == Booking.venue_space_id)
        .where(
            MatchParticipant.user_id == user_id,
            MatchParticipant.status == "checked_in",
            Match.state == "FINALIZED",
        )
    )
    aggregated: dict[uuid.UUID, CourtTotals] = {}
    for space_id, name, result, team, scheduled in session.execute(statement):
        entry = aggregated.get(space_id)
        if entry is None:
            entry = CourtTotals(
                space_id=space_id,
                name=name,
                matches=0,
                wins=0,
                last_played_at=ensure_utc(scheduled),
            )
            aggregated[space_id] = entry
        entry.matches += 1
        if result == f"TEAM_{team}":
            entry.wins += 1
        entry.last_played_at = max(entry.last_played_at, ensure_utc(scheduled))
    return sorted(aggregated.values(), key=lambda item: item.matches, reverse=True)


def own_hours(session: Session, user_id: uuid.UUID, *, limit: int = 3) -> list[str]:
    """Faixas em que o jogador mais jogou. Nunca expõe horário de outra pessoa."""

    statement = (
        select(Match.scheduled_start_at)
        .join(MatchParticipant, MatchParticipant.match_id == Match.id)
        .where(
            MatchParticipant.user_id == user_id,
            MatchParticipant.status == "checked_in",
            Match.state == "FINALIZED",
        )
    )
    counts = Counter(band_for(moment) for moment in session.scalars(statement))
    return [band for band, _ in counts.most_common(limit)]


def network_cells(
    session: Session,
    *,
    now: datetime | None = None,
) -> tuple[list[NetworkCell], int]:
    """Agrega partidas concluídas por quadra e faixa nos últimos 30 dias.

    Devolve apenas células com amostra mínima; o total amostral inclui tudo.
    """

    moment = now or utcnow()
    since = moment - timedelta(days=NETWORK_WINDOW_DAYS)
    statement = (
        select(
            VenueSpace.id,
            VenueSpace.name,
            Match.scheduled_start_at,
            Match.id,
        )
        .join(Booking, Booking.lobby_id == Match.lobby_id)
        .join(VenueSpace, VenueSpace.id == Booking.venue_space_id)
        .where(
            Match.state == "FINALIZED",
            Match.scheduled_start_at >= since,
        )
    )
    counts: Counter[tuple[uuid.UUID, str, str]] = Counter()
    sample = 0
    for space_id, name, scheduled, _match_id in session.execute(statement):
        counts[(space_id, name, band_for(scheduled))] += 1
        sample += 1

    cells: list[NetworkCell] = []
    for (space_id, name, band), matches in counts.items():
        if matches < NETWORK_MIN_SAMPLE:
            continue
        level = "alta" if matches >= NETWORK_MIN_SAMPLE * 2 else "média"
        cells.append(
            NetworkCell(
                space_id=space_id,
                space_name=name,
                band=band,
                matches=matches,
                level=level,
            )
        )
    cells.sort(key=lambda item: (item.space_name, item.band))
    return cells, sample


def network_venues(
    session: Session,
    *,
    now: datetime | None = None,
) -> tuple[list[tuple[uuid.UUID, str, int, str]], int]:
    """Quadras com mais partidas na janela, sem quebrar por faixa."""

    moment = now or utcnow()
    since = moment - timedelta(days=NETWORK_WINDOW_DAYS)
    statement = (
        select(VenueSpace.id, VenueSpace.name, Match.id)
        .join(Booking, Booking.lobby_id == Match.lobby_id)
        .join(VenueSpace, VenueSpace.id == Booking.venue_space_id)
        .where(
            Match.state == "FINALIZED",
            Match.scheduled_start_at >= since,
        )
    )
    counts: Counter[tuple[uuid.UUID, str]] = Counter()
    sample = 0
    for space_id, name, _match_id in session.execute(statement):
        counts[(space_id, name)] += 1
        sample += 1
    venues = [
        (
            space_id,
            name,
            matches,
            "alta" if matches >= NETWORK_MIN_SAMPLE * 2 else "média",
        )
        for (space_id, name), matches in counts.items()
        if matches >= NETWORK_MIN_SAMPLE
    ]
    venues.sort(key=lambda item: item[2], reverse=True)
    return venues, sample


def network_peak_band(session: Session, *, now: datetime | None = None) -> str | None:
    """Faixa com mais partidas na janela. Nunca identifica pessoa ou quadra."""

    moment = now or utcnow()
    since = moment - timedelta(days=NETWORK_WINDOW_DAYS)
    statement = select(Match.scheduled_start_at).where(
        Match.state == "FINALIZED",
        Match.scheduled_start_at >= since,
    )
    counts = Counter(band_for(moment_) for moment_ in session.scalars(statement))
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def network_updated_on(now: datetime | None = None) -> date:
    """A rede é atualizada uma vez por dia; a data é a referência da leitura."""

    return (now or utcnow()).date()
