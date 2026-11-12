"""Testes de temporada, XP e streak (Fase 14D.7)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.season.service import (
    XP_PER_LEVEL,
    XpConflict,
    award_xp,
    effective_streak,
    level_for,
    record_match_result,
    seed_current_season,
    streak_for,
    tier_for,
)
from tests.helpers_results import make_token, make_user

MONDAY = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_level_and_tier_boundaries() -> None:
    assert level_for(0) == 0
    assert level_for(XP_PER_LEVEL - 1) == 0
    assert level_for(XP_PER_LEVEL) == 1
    assert level_for(XP_PER_LEVEL * 30) == 30
    assert level_for(XP_PER_LEVEL * 99) == 30
    assert tier_for(0) == "bronze"
    assert tier_for(9) == "bronze"
    assert tier_for(10) == "prata"
    assert tier_for(19) == "prata"
    assert tier_for(20) == "ouro"


def test_award_xp_is_idempotent(db_session: Session) -> None:
    user_id = make_user(db_session)
    season = seed_current_season(db_session)

    first = award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=100,
        source="match",
        idempotency_key="match:1",
    )
    second = award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=100,
        source="match",
        idempotency_key="match:1",
    )
    assert first.xp_total == 100
    assert second.xp_total == 100

    with pytest.raises(XpConflict):
        award_xp(
            db_session,
            user_id=user_id,
            season=season,
            amount=50,
            source="match",
            idempotency_key="match:1",
        )


def test_level_follows_accumulated_xp(db_session: Session) -> None:
    user_id = make_user(db_session)
    season = seed_current_season(db_session)
    for index in range(3):
        award_xp(
            db_session,
            user_id=user_id,
            season=season,
            amount=XP_PER_LEVEL,
            source="match",
            idempotency_key=f"match:{index}",
        )
    record = award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=XP_PER_LEVEL,
        source="match",
        idempotency_key="match:3",
    )
    assert record.xp_total == XP_PER_LEVEL * 4
    assert record.level == 4


def test_win_streak_increments_and_loss_resets(db_session: Session) -> None:
    user_id = make_user(db_session)
    match = uuid.uuid4()

    record = record_match_result(
        db_session, user_id, match_id=match, won=True, played_at=MONDAY
    )
    record = record_match_result(
        db_session, user_id, match_id=match, won=True, played_at=MONDAY
    )
    assert record.current_wins == 2
    assert record.best_wins == 2

    record = record_match_result(
        db_session, user_id, match_id=match, won=False, played_at=MONDAY
    )
    assert record.current_wins == 0
    assert record.best_wins == 2


def test_streak_expires_after_a_full_empty_week(db_session: Session) -> None:
    user_id = make_user(db_session)
    record_match_result(
        db_session, user_id, match_id=uuid.uuid4(), won=True, played_at=MONDAY
    )
    record = streak_for(db_session, user_id)

    assert effective_streak(record, MONDAY + timedelta(days=5)) == 1
    assert effective_streak(record, MONDAY + timedelta(days=10)) == 1
    assert effective_streak(record, MONDAY + timedelta(days=17)) == 0


def test_progress_endpoint_returns_season_and_streak(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    season = seed_current_season(db_session)
    award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=XP_PER_LEVEL * 2,
        source="match",
        idempotency_key=f"match:{user_id}",
    )
    db_session.commit()

    response = api.get("/api/v1/me/progress", headers=bearer(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["season"]["code"] == season.code
    assert body["xp_total"] == XP_PER_LEVEL * 2
    assert body["level"] == 2
    assert body["tier"] == "bronze"
    assert body["next_level_xp"] == XP_PER_LEVEL * 3
    assert body["streak"] == {"current": 0, "best": 0}
