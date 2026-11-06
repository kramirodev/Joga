"""Testes HTTP de leitura de rating e ranking."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import SessionService
from app.modules.profile.models import UserProfile
from app.modules.ratings.models import ALGORITHM_VERSION, RatingAccount
from tests.helpers_results import make_format, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_user_with_token(session: Session) -> tuple[uuid.UUID, str]:
    user_id = make_user(session)
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    session.commit()
    return user_id, tokens.access_token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_account(
    session: Session,
    user_id: uuid.UUID,
    format_id: uuid.UUID,
    *,
    rating: float,
    matches_played: int = 10,
    display_name: str | None = None,
) -> RatingAccount:
    if display_name is not None:
        session.add(UserProfile(user_id=user_id, display_name=display_name))
    account = RatingAccount(
        user_id=user_id,
        format_id=format_id,
        rating=rating,
        rating_deviation=80.0,
        volatility=0.06,
        matches_played=matches_played,
        algorithm_version=ALGORITHM_VERSION,
        last_rated_at=datetime(2026, 11, 6, tzinfo=UTC),
    )
    session.add(account)
    session.flush()
    return account


def test_rating_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/v1/ratings/me?format_id={uuid.uuid4()}")
    assert response.status_code == 401


def test_new_player_is_provisional_without_raw_mmr(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id, token = make_user_with_token(db_session)
    _, sport_format = make_format(db_session)
    db_session.commit()

    response = api.get(
        f"/api/v1/ratings/me?format_id={sport_format.id}",
        headers=bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["division"] == "PROVISIONAL"
    assert body["provisional"] is True
    assert body["placement_matches_remaining"] == 5
    assert body["position"] is None
    assert "rating" not in body
    assert body["matches_played"] == 0


def test_player_card_shows_division_and_position(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id, token = make_user_with_token(db_session)
    _, sport_format = make_format(db_session)
    add_account(db_session, user_id, sport_format.id, rating=1750, display_name="Ana")
    db_session.commit()

    response = api.get(
        f"/api/v1/ratings/me?format_id={sport_format.id}",
        headers=bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["division"] == "PLATINUM"
    assert body["provisional"] is False
    assert body["position"] == 1
    assert body["progress"] == 0.75
    assert "rating" not in body
    assert "rating_deviation" not in body
    assert "trust" not in body


def test_ranking_orders_by_mmr_and_excludes_provisional(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    _, token = make_user_with_token(db_session)
    _, sport_format = make_format(db_session)

    high_user = make_user(db_session)
    low_user = make_user(db_session)
    provisional_user = make_user(db_session)
    add_account(db_session, high_user, sport_format.id, rating=1900, display_name="Alta")
    add_account(db_session, low_user, sport_format.id, rating=1500, display_name="Baixa")
    add_account(
        db_session,
        provisional_user,
        sport_format.id,
        rating=2500,
        matches_played=2,
        display_name="Provisória",
    )
    db_session.commit()

    response = api.get(
        f"/api/v1/rankings?format_id={sport_format.id}",
        headers=bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [entry["display_name"] for entry in body["entries"]] == ["Alta", "Baixa"]
    assert [entry["position"] for entry in body["entries"]] == [1, 2]
    assert body["entries"][0]["division"] == "DIAMOND"
    assert body["entries"][1]["division"] == "GOLD"
    assert "rating" not in body["entries"][0]


def test_ranking_paginates(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    _, token = make_user_with_token(db_session)
    _, sport_format = make_format(db_session)
    for index in range(3):
        user_id = make_user(db_session)
        add_account(
            db_session,
            user_id,
            sport_format.id,
            rating=1600 + index * 10,
            display_name=f"Jogador {index}",
        )
    db_session.commit()

    response = api.get(
        f"/api/v1/rankings?format_id={sport_format.id}&limit=1&offset=1",
        headers=bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["entries"]) == 1
    assert body["entries"][0]["position"] == 2


def test_unknown_format_returns_404(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, token = make_user_with_token(db_session)
    db_session.commit()

    response = api.get(
        f"/api/v1/rankings?format_id={uuid.uuid4()}",
        headers=bearer(token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "format_not_found"}}
