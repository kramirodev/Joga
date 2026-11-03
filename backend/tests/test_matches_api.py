"""Testes da API de partidas."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matches.service import create_match_for_lobby
from app.modules.matchmaking.models import Lobby, LobbyParticipant, QueueEntry
from app.modules.profile.models import (
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)


@pytest.fixture
def api(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_user(session: Session) -> uuid.UUID:
    user = User(status="active")
    session.add(user)
    session.flush()
    return user.id


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


def build_match(session: Session, *, start_delta_hours: int = 48) -> tuple[Match, list[uuid.UUID]]:
    now = datetime.now(UTC)
    start = now + timedelta(hours=start_delta_hours)
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
            expires_at=now + timedelta(hours=48),
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

    match = create_match_for_lobby(session, lobby, participants, now=now)
    session.commit()
    return match, users


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_matches_require_authentication(api: TestClient) -> None:
    assert api.get("/api/v1/matches").status_code == 401


def test_only_participants_see_match(api: TestClient, db_session: Session) -> None:
    match, _ = build_match(db_session)
    outsider = make_user(db_session)
    token = make_token(db_session, outsider)

    assert api.get(f"/api/v1/matches/{match.id}", headers=bearer(token)).status_code == 404
    assert api.post(f"/api/v1/matches/{match.id}/confirm", headers=bearer(token)).status_code == 404


def test_participant_lists_and_confirms_idempotently(
    api: TestClient,
    db_session: Session,
) -> None:
    match, users = build_match(db_session)
    token = make_token(db_session, users[0])

    listing = api.get("/api/v1/matches", headers=bearer(token))
    assert listing.status_code == 200
    assert listing.json()["matches"][0]["id"] == str(match.id)

    first = api.post(f"/api/v1/matches/{match.id}/confirm", headers=bearer(token))
    second = api.post(f"/api/v1/matches/{match.id}/confirm", headers=bearer(token))

    assert first.status_code == 200
    assert first.json()["my_status"] == "confirmed"
    assert second.status_code == 200
    assert second.json()["my_status"] == "confirmed"
    assert second.json()["state"] == "PENDING_CONFIRMATION"

    detail = api.get(f"/api/v1/matches/{match.id}", headers=bearer(token))
    assert detail.status_code == 200
    assert len(detail.json()["participants"]) == 10


def test_all_confirm_makes_match_ready(api: TestClient, db_session: Session) -> None:
    match, users = build_match(db_session)
    tokens = [make_token(db_session, user_id) for user_id in users]

    for token in tokens:
        response = api.post(f"/api/v1/matches/{match.id}/confirm", headers=bearer(token))
        assert response.status_code == 200

    assert response.json()["state"] == "READY"
    assert sum(1 for item in response.json()["participants"] if item["status"] == "confirmed") == 10


def test_decline_cancels_match(api: TestClient, db_session: Session) -> None:
    match, users = build_match(db_session)
    token = make_token(db_session, users[0])

    response = api.post(f"/api/v1/matches/{match.id}/decline", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["state"] == "CANCELLED"
    assert response.json()["cancelled_reason"] == "declined"


def test_check_in_respects_window(api: TestClient, db_session: Session) -> None:
    match, users = build_match(db_session)
    now = datetime.now(UTC)
    match.state = "READY"
    match.check_in_opens_at = now - timedelta(minutes=5)
    match.check_in_deadline = now + timedelta(minutes=5)
    participant = db_session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match.id,
            MatchParticipant.user_id == users[0],
        )
    )
    assert participant is not None
    participant.status = "confirmed"
    db_session.commit()
    token = make_token(db_session, users[0])

    response = api.post(f"/api/v1/matches/{match.id}/check-in", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["my_status"] == "checked_in"

    closed = api.post(f"/api/v1/matches/{match.id}/check-in", headers=bearer(token))
    assert closed.status_code == 200  # idempotente
