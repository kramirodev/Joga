"""Fábricas compartilhadas dos testes de resultados (Fase 7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matches.service import create_match_for_lobby
from app.modules.matchmaking.models import Lobby, LobbyParticipant, QueueEntry
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)

NOW = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)
START = datetime(2026, 11, 7, 21, 0, tzinfo=UTC)
END = START + timedelta(minutes=60)


def make_token(session: Session, user_id: uuid.UUID) -> str:
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    session.commit()
    return tokens.access_token


def make_user(session: Session, *, available: bool = True) -> uuid.UUID:
    user = User(status="active")
    session.add(user)
    session.flush()
    if available:
        session.add(
            Availability(
                user_id=user.id,
                weekday=6,
                start_time=time(18, 0),
                end_time=time(23, 0),
                timezone="America/Sao_Paulo",
            )
        )
    session.flush()
    return user.id


def make_format(
    session: Session,
    *,
    sport_slug: str = "futebol",
    team_size: int = 5,
) -> tuple[Sport, SportFormat]:
    sport = session.scalar(select(Sport).where(Sport.slug == sport_slug))
    if sport is None:
        sport = Sport(slug=sport_slug, name=sport_slug.title())
        session.add(sport)
        session.flush()
    total = team_size * 2
    format_slug = f"{sport_slug}-{team_size}x{team_size}"
    sport_format = session.scalar(
        select(SportFormat).where(
            SportFormat.slug == format_slug,
            SportFormat.version == 1,
        )
    )
    if sport_format is None:
        sport_format = SportFormat(
            sport_id=sport.id,
            slug=format_slug,
            name=f"{sport_slug.title()} {team_size}x{team_size}",
            team_size=team_size,
            total_participants=total,
            play_minutes=50,
            break_minutes=10,
            duration_minutes=60,
            version=1,
        )
        session.add(sport_format)
        session.flush()
    return sport, sport_format


def add_finalized_history(
    session: Session,
    sport_format: SportFormat,
    user_ids: list[uuid.UUID],
    *,
    count: int,
    before: datetime,
) -> None:
    """Cria partidas finalizadas anteriores para alimentar a escolha do capitão."""
    for index in range(count):
        start = before - timedelta(days=2 + index, hours=2)
        lobby = Lobby(
            format_id=sport_format.id,
            format_version=1,
            origin="matchmaking",
            mode="casual",
            status="completed",
            court_preference="ANY",
            scheduled_start_at=start,
            scheduled_end_at=start + timedelta(minutes=60),
            duration_minutes=60,
            center_lat=-23.55,
            center_lng=-46.63,
            radius_km=10,
            algorithm_version="level_v1",
        )
        session.add(lobby)
        session.flush()
        match = Match(
            lobby_id=lobby.id,
            state="FINALIZED",
            scheduled_start_at=start,
            scheduled_end_at=start + timedelta(minutes=60),
            confirmation_deadline=start - timedelta(hours=24),
            check_in_opens_at=start - timedelta(hours=1),
            check_in_deadline=start - timedelta(minutes=30),
            substitution_deadline=start - timedelta(minutes=15),
            final_result="TEAM_1",
            finalized_at=start + timedelta(minutes=60),
        )
        session.add(match)
        session.flush()
        for position, user_id in enumerate(user_ids):
            session.add(
                MatchParticipant(
                    match_id=match.id,
                    user_id=user_id,
                    team=1 if position < len(user_ids) // 2 else 2,
                    level="intermediate",
                    status="checked_in",
                )
            )
        session.flush()


def build_match(
    session: Session,
    *,
    sport_slug: str = "futebol",
    team_size: int = 5,
    state: str = "IN_PROGRESS",
    checked_in: int | None = None,
    history: dict[int, int] | None = None,
    origin: str = "matchmaking",
    mode: str = "casual",
    start: datetime = START,
    end: datetime = END,
) -> tuple[Match, list[uuid.UUID], list[MatchParticipant], SportFormat]:
    """Monta uma partida completa e retorna participantes na ordem de criação."""
    _, sport_format = make_format(session, sport_slug=sport_slug, team_size=team_size)
    total = team_size * 2

    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin=origin,
        mode=mode,
        status="scheduled",
        court_preference="ANY",
        scheduled_start_at=start,
        scheduled_end_at=end,
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()

    users: list[uuid.UUID] = []
    lobby_participants: list[LobbyParticipant] = []
    for index in range(total):
        user_id = make_user(session)
        users.append(user_id)
        session.add(
            UserRegion(
                user_id=user_id,
                source="cep",
                cep="01001000",
                city="São Paulo",
                state="SP",
                radius_km=10,
                center_lat=-23.55,
                center_lng=-46.63,
            )
        )
        session.add(
            UserSportProfile(
                user_id=user_id,
                format_id=sport_format.id,
                level="intermediate",
                court_preference="ANY",
            )
        )
        entry = QueueEntry(
            user_id=user_id,
            format_id=sport_format.id,
            mode="casual",
            court_preference="ANY",
            level="intermediate",
            status="matched",
            center_lat=-23.55,
            center_lng=-46.63,
            radius_km=10,
            lobby_id=lobby.id,
            created_at=NOW - timedelta(minutes=total - index),
            expires_at=NOW + timedelta(hours=24),
        )
        session.add(entry)
        session.flush()
        participant = LobbyParticipant(
            lobby_id=lobby.id,
            user_id=user_id,
            queue_entry_id=entry.id,
            team=1 if index < team_size else 2,
            level="intermediate",
        )
        session.add(participant)
        lobby_participants.append(participant)
    session.flush()

    for index, count in (history or {}).items():
        add_finalized_history(
            session,
            sport_format,
            [users[index]],
            count=count,
            before=start,
        )

    match = create_match_for_lobby(session, lobby, lobby_participants, now=NOW)
    participants = list(
        session.query(MatchParticipant)
        .filter(MatchParticipant.match_id == match.id)
        .order_by(MatchParticipant.team, MatchParticipant.user_id)
        .all()
    )
    confirmed = total if checked_in is None else total - checked_in
    for index, participant in enumerate(participants):
        if index < confirmed:
            participant.status = "confirmed"
            participant.confirmed_at = NOW
        else:
            participant.status = "checked_in"
            participant.confirmed_at = NOW
            participant.checked_in_at = START - timedelta(minutes=10)
    if state == "IN_PROGRESS":
        match.started_at = start
    match.state = state
    session.flush()
    return match, users, participants, sport_format
