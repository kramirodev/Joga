"""Testes do ciclo de vida da partida (serviço)."""

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.matches.models import Match, MatchParticipant, MatchStateTransition
from app.modules.matches.service import (
    ActionNotAllowed,
    CheckInClosed,
    InvalidTransition,
    MatchService,
    create_match_for_lobby,
    transition,
)
from app.modules.matchmaking.models import Lobby, LobbyParticipant, QueueEntry
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
START = datetime(2026, 11, 4, 21, 0, tzinfo=UTC)  # quarta 18:00 em São Paulo
END = START + timedelta(minutes=60)


def make_user(session: Session, *, available: bool = True) -> uuid.UUID:
    from app.modules.identity.models import User

    user = User(status="active")
    session.add(user)
    session.flush()
    if available:
        session.add(
            Availability(
                user_id=user.id,
                weekday=3,
                start_time=time(18, 0),
                end_time=time(22, 0),
                timezone="America/Sao_Paulo",
            )
        )
    session.flush()
    return user.id


def build_match(
    session: Session,
    *,
    confirmed: int = 0,
    checked_in: int = 0,
    extra_waiting: int = 0,
    state: str | None = None,
) -> tuple[Match, list[uuid.UUID]]:
    sport = Sport(slug="futebol", name="Futebol")
    session.add(sport)
    session.flush()
    sport_format = SportFormat(
        sport_id=sport.id,
        slug="futebol-5x5",
        name="Futebol 5x5",
        team_size=5,
        total_participants=10,
        play_minutes=50,
        break_minutes=10,
        duration_minutes=60,
        version=1,
    )
    session.add(sport_format)
    session.flush()

    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin="matchmaking",
        mode="casual",
        status="scheduled",
        court_preference="ANY",
        scheduled_start_at=START,
        scheduled_end_at=END,
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()

    users: list[uuid.UUID] = []
    participants: list[LobbyParticipant] = []
    for index in range(10):
        user_id = make_user(session)
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
            created_at=NOW - timedelta(minutes=10 - index),
            expires_at=NOW + timedelta(hours=24),
        )
        session.add(entry)
        session.flush()
        participant = LobbyParticipant(
            lobby_id=lobby.id,
            user_id=user_id,
            queue_entry_id=entry.id,
            team=1 if index < 5 else 2,
            level="intermediate",
        )
        session.add(participant)
        participants.append(participant)
        users.append(user_id)
    session.flush()

    for _ in range(extra_waiting):
        user_id = make_user(session)
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
            QueueEntry(
                user_id=user_id,
                format_id=sport_format.id,
                mode="casual",
                court_preference="ANY",
                level="intermediate",
                status="waiting",
                center_lat=-23.55,
                center_lng=-46.63,
                radius_km=10,
                expires_at=NOW + timedelta(hours=24),
            )
        )
    session.flush()

    match = create_match_for_lobby(session, lobby, participants, now=NOW)
    rows = list(
        session.scalars(
            select(MatchParticipant)
            .where(MatchParticipant.match_id == match.id)
            .order_by(MatchParticipant.team, MatchParticipant.user_id)
        )
    )
    for index, row in enumerate(rows):
        if index < checked_in:
            row.status = "checked_in"
            row.confirmed_at = NOW
            row.checked_in_at = NOW + timedelta(hours=30)
        elif index < confirmed + checked_in:
            row.status = "confirmed"
            row.confirmed_at = NOW
    session.flush()

    if state is not None:
        match.state = state
    elif confirmed + checked_in == 10:
        match.state = "READY"
    session.flush()
    return match, users


def test_confirm_requires_all_participants(db_session: Session) -> None:
    match, users = build_match(db_session)
    service = MatchService(db_session)

    for user_id in users[:9]:
        service.confirm(match.id, user_id, now=NOW)
    assert match.state == "PENDING_CONFIRMATION"

    service.confirm(match.id, users[9], now=NOW)
    assert match.state == "READY"

    ready_events = db_session.scalars(
        select(MatchStateTransition).where(
            MatchStateTransition.match_id == match.id,
            MatchStateTransition.to_state == "READY",
        )
    ).all()
    assert len(ready_events) == 1


def test_confirm_is_idempotent(db_session: Session) -> None:
    match, users = build_match(db_session)
    service = MatchService(db_session)

    service.confirm(match.id, users[0], now=NOW)
    service.confirm(match.id, users[0], now=NOW)

    rows = db_session.scalars(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match.id, MatchParticipant.user_id == users[0]
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "confirmed"


def test_decline_dissolves_and_requeues_confirmed(db_session: Session) -> None:
    match, users = build_match(db_session)
    service = MatchService(db_session)
    for user_id in users[:9]:
        service.confirm(match.id, user_id, now=NOW)

    service.decline(match.id, users[9], now=NOW)

    assert match.state == "CANCELLED"
    assert match.cancelled_reason == "declined"

    waiting = db_session.scalars(
        select(QueueEntry).where(
            QueueEntry.format_id == db_session.get(Lobby, match.lobby_id).format_id,
            QueueEntry.status == "waiting",
        )
    ).all()
    assert len(waiting) == 9
    declined_entry = db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == users[9]))
    assert declined_entry is not None and declined_entry.status == "cancelled"


def test_deadline_without_all_confirmations_dissolves(db_session: Session) -> None:
    match, users = build_match(db_session)
    service = MatchService(db_session)
    for user_id in users[:9]:
        service.confirm(match.id, user_id, now=NOW)

    result = service.advance(now=datetime(2026, 11, 4, 10, 1, tzinfo=UTC))

    assert result.confirmed_expired == 1
    assert match.state == "CANCELLED"
    assert match.cancelled_reason == "confirmation_deadline"


def test_check_in_only_within_window(db_session: Session) -> None:
    match, users = build_match(db_session, confirmed=10)
    service = MatchService(db_session)

    with pytest.raises(CheckInClosed):
        service.check_in(match.id, users[0], now=NOW)

    with pytest.raises(CheckInClosed):
        service.check_in(match.id, users[0], now=START + timedelta(minutes=1))

    service.check_in(match.id, users[0], now=START - timedelta(minutes=55))
    row = db_session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match.id, MatchParticipant.user_id == users[0]
        )
    )
    assert row is not None and row.status == "checked_in"


def test_all_checked_in_starts_match(db_session: Session) -> None:
    match, _ = build_match(db_session, checked_in=10)

    result = MatchService(db_session).advance(now=START)

    assert result.started == 1
    assert match.state == "IN_PROGRESS"


def test_missing_check_in_invites_substitute(db_session: Session) -> None:
    match, users = build_match(db_session, confirmed=1, checked_in=9, extra_waiting=1)
    service = MatchService(db_session)

    result = service.advance(now=START - timedelta(minutes=29))

    assert result.substitutes_invited == 1
    missing = db_session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match.id,
            MatchParticipant.status == "no_show",
        )
    )
    assert missing is not None
    assert missing.is_substitute is False
    substitute = db_session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match.id,
            MatchParticipant.is_substitute.is_(True),
        )
    )
    assert substitute is not None and substitute.status == "invited"

    service.confirm(match.id, substitute.user_id, now=START - timedelta(minutes=28))
    service.check_in(match.id, substitute.user_id, now=START - timedelta(minutes=27))

    started = service.advance(now=START)
    assert started.started == 1
    assert match.state == "IN_PROGRESS"


def test_missing_check_in_without_substitute_cancels(db_session: Session) -> None:
    match, _ = build_match(db_session, confirmed=1, checked_in=9)
    service = MatchService(db_session)

    result = service.advance(now=START - timedelta(minutes=14))

    assert result.cancelled == 1
    assert match.state == "CANCELLED"
    assert match.cancelled_reason == "no_substitute"


def test_invalid_transition_is_rejected(db_session: Session) -> None:
    match, _ = build_match(db_session, checked_in=10)

    with pytest.raises(InvalidTransition):
        transition(db_session, match, "READY")


def test_action_after_cancel_is_rejected(db_session: Session) -> None:
    match, users = build_match(db_session, checked_in=10)
    transition(db_session, match, "CANCELLED", reason="test")

    with pytest.raises(ActionNotAllowed):
        MatchService(db_session).decline(match.id, users[0], now=START)
