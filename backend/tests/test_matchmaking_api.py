"""Testes da API de fila de matchmaking."""

from collections.abc import Iterator
from datetime import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.profile.models import (
    Availability,
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


def make_user_with_tokens(session: Session) -> tuple[UUID, str]:
    user = User(status="active")
    session.add(user)
    session.flush()
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id)
    session.commit()
    return user.id, tokens.access_token


def seed_format(session: Session) -> SportFormat:
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
    return sport_format


def give_region(session: Session, user_id: UUID) -> None:
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
    session.flush()


def give_sport_profile(
    session: Session,
    user_id: UUID,
    format_id: UUID,
    *,
    level: str = "intermediate",
    court: str = "ANY",
) -> None:
    session.add(
        UserSportProfile(
            user_id=user_id,
            format_id=format_id,
            level=level,
            court_preference=court,
        )
    )
    session.flush()


def give_availability(session: Session, user_id: UUID) -> None:
    session.add(
        Availability(
            user_id=user_id,
            weekday=2,
            start_time=time(18, 0),
            end_time=time(22, 0),
            timezone="America/Sao_Paulo",
        )
    )
    session.flush()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_queue_requires_authentication(api: TestClient) -> None:
    assert api.get("/api/v1/matchmaking/queue").status_code == 401
    assert api.post("/api/v1/matchmaking/queue", json={}).status_code == 401


def test_enqueue_requires_region(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "region_required"}}


def test_enqueue_requires_sport_profile(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "sport_profile_required"}}


def test_enqueue_accepts_ranked(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "mode": "ranked"},
    )

    assert response.status_code == 201
    assert response.json()["mode"] == "ranked"


def test_enqueue_rejects_unknown_format(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    give_region(db_session, user_id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_format"}}


def test_enqueue_and_leave(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, court="PUBLIC_ONLY")

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "waiting"
    assert body["mode"] == "casual"
    assert body["court_preference"] == "PUBLIC_ONLY"
    assert body["level"] == "intermediate"
    assert body["radius_km"] == 10
    assert body["lobby"] is None
    assert "center_lat" not in body and "center_lng" not in body

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token))
    assert state.status_code == 200
    assert state.json()["entry"]["id"] == body["id"]

    left = api.delete("/api/v1/matchmaking/queue", headers=bearer(token))
    assert left.status_code == 204

    empty = api.get("/api/v1/matchmaking/queue", headers=bearer(token))
    assert empty.json() == {"entry": None}

    again = api.delete("/api/v1/matchmaking/queue", headers=bearer(token))
    assert again.status_code == 404
    assert again.json() == {"detail": {"code": "not_queued"}}


def test_enqueue_rejects_duplicate(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)
    payload = {"format_id": str(sport_format.id)}

    first = api.post("/api/v1/matchmaking/queue", headers=bearer(token), json=payload)
    second = api.post("/api/v1/matchmaking/queue", headers=bearer(token), json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": {"code": "already_queued"}}


def test_enqueue_overrides_court_preference(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, court="ANY")

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "court_preference": "PRIVATE_ONLY"},
    )

    assert created.status_code == 201
    assert created.json()["court_preference"] == "PRIVATE_ONLY"


def test_enqueue_accepts_without_availability(api: TestClient, db_session: Session) -> None:
    """A ausência de agenda não impede entrar na fila; só impede a formação."""
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert created.status_code == 201
