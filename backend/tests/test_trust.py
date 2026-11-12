"""Testes do Trust Factor interno (ADR 0041)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ratings.models import TrustAccount, TrustEvent
from app.modules.ratings.trust import TrustService
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import api_client
from tests.test_matchmaking_api import (
    bearer,
    give_region,
    give_sport_profile,
    seed_format,
)


def test_no_show_penalty_recurrence_and_restriction(db_session: Session) -> None:
    user = make_user(db_session)
    service = TrustService(db_session)
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    first = service.apply_event(user, "no_show", now=now)
    second = service.apply_event(user, "no_show", now=now)
    third = service.apply_event(user, "no_show", now=now)
    db_session.flush()

    assert first.details["delta"] == -30
    assert second.details["delta"] == -45
    assert third.details["delta"] == -60
    account = db_session.get(TrustAccount, user)
    assert account is not None and account.score == 0
    assert account.ranked_restricted_until is not None
    assert account.ranked_restricted_until.replace(tzinfo=UTC) >= now + timedelta(days=30)


def test_cancel_penalties_and_recovery(db_session: Session) -> None:
    user = make_user(db_session)
    service = TrustService(db_session)
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    cancel_before = service.apply_event(user, "cancel_before_payment", now=now)
    cancel_after = service.apply_event(user, "cancel_after_confirmation", now=now)
    assert cancel_before.details["delta"] == -2
    assert cancel_after.details["delta"] == -11

    recovery_user = make_user(db_session)
    TrustService(db_session).apply_event(recovery_user, "no_show", now=now)
    first = TrustService(db_session).apply_event(recovery_user, "match_completed", now=now)
    second = TrustService(db_session).apply_event(recovery_user, "match_completed", now=now)
    assert first.details["delta"] == 6
    assert second.details["delta"] == 5
    account = db_session.get(TrustAccount, recovery_user)
    assert account is not None and account.score == 81


def test_ranked_restriction_blocks_only_ranked_queue(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user = make_user(db_session)
    token = make_token(db_session, user)
    sport_format = seed_format(db_session)
    give_region(db_session, user)
    give_sport_profile(db_session, user, sport_format.id)
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    service = TrustService(db_session)
    service.apply_event(user, "no_show", now=now)
    service.apply_event(user, "no_show", now=now)
    db_session.commit()

    blocked = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "mode": "ranked"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "ranked_restricted"

    casual = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "mode": "casual"},
    )
    assert casual.status_code == 201, casual.text


def test_restriction_expires(db_session: Session) -> None:
    user = make_user(db_session)
    account = TrustAccount(user_id=user, score=50)
    db_session.add(account)
    db_session.flush()
    service = TrustService(db_session)
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    account.ranked_restricted_until = now - timedelta(minutes=1)
    assert service.is_ranked_restricted(user, now=now) is False
    account.ranked_restricted_until = now + timedelta(days=1)
    assert service.is_ranked_restricted(user, now=now) is True

    events = db_session.scalars(select(TrustEvent).where(TrustEvent.user_id == user)).all()
    assert events == []
