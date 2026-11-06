"""Testes do serviço de aplicação de MMR e Trust Factor."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.matches.service import MatchNotFound
from app.modules.matchmaking.models import Lobby
from app.modules.ratings.models import RatingAccount, RatingEvent, TrustAccount, TrustEvent
from app.modules.ratings.service import RatingNotApplicable, RatingService
from tests.helpers_results import END, build_match

AT = END + timedelta(minutes=2)


def finalize_match(
    session: Session,
    *,
    mode: str = "ranked",
    state: str = "FINALIZED",
    result: str = "TEAM_1",
):
    match, users, participants, _ = build_match(session, checked_in=10, mode=mode)
    match.state = state
    match.final_result = result if state == "FINALIZED" else None
    match.finalized_at = END if state == "FINALIZED" else None
    match.updated_at = END
    session.flush()
    return match, users, participants


def test_apply_rating_updates_accounts_and_events_once(db_session: Session) -> None:
    match, users, _ = finalize_match(db_session)

    result = RatingService(db_session).apply_match(match.id, now=AT)

    assert result.applied == 10
    assert result.already_applied is False
    events = list(db_session.scalars(select(RatingEvent).where(RatingEvent.match_id == match.id)))
    assert len(events) == 10
    assert {event.result for event in events} == {"WIN", "LOSS"}

    accounts = {
        account.user_id: account
        for account in db_session.scalars(
            select(RatingAccount).where(RatingAccount.format_id == events[0].format_id)
        )
    }
    assert len(accounts) == 10
    winner_ids = set(users[:5])
    assert all(accounts[user_id].rating > 1500 for user_id in winner_ids)
    assert all(accounts[user_id].rating < 1500 for user_id in set(users) - winner_ids)
    assert all(account.matches_played == 1 for account in accounts.values())

    second = RatingService(db_session).apply_match(match.id, now=AT)
    assert second.already_applied is True
    assert second.applied == 0
    assert (
        db_session.scalar(
            select(func.count()).select_from(RatingEvent).where(RatingEvent.match_id == match.id)
        )
        == 10
    )


def test_casual_match_does_not_apply_rating(db_session: Session) -> None:
    match, _, _ = finalize_match(db_session, mode="casual")

    with pytest.raises(RatingNotApplicable):
        RatingService(db_session).apply_match(match.id, now=AT)

    assert db_session.scalar(select(func.count()).select_from(RatingEvent)) == 0


@pytest.mark.parametrize("state", ["DISPUTED", "VOIDED", "IN_PROGRESS", "RESULT_PENDING"])
def test_non_finalized_or_disputed_match_does_not_apply_rating(
    db_session: Session,
    state: str,
) -> None:
    match, _, _ = finalize_match(db_session, state=state)

    with pytest.raises(RatingNotApplicable):
        RatingService(db_session).apply_match(match.id, now=AT)

    assert db_session.scalar(select(func.count()).select_from(RatingEvent)) == 0


def test_pending_match_ids_skip_already_rated(db_session: Session) -> None:
    match, _, _ = finalize_match(db_session)
    service = RatingService(db_session)

    assert service.pending_match_ids() == [match.id]
    service.apply_match(match.id, now=AT)
    db_session.commit()

    assert service.pending_match_ids() == []


def test_trust_event_is_appended_without_changing_neutral_score(db_session: Session) -> None:
    match, users, _ = finalize_match(db_session)
    service = RatingService(db_session)

    event = service.record_trust_event(
        users[0],
        "no_show",
        match_id=match.id,
        severity=2,
        details={"source": "test"},
        now=AT,
    )

    account = db_session.get(TrustAccount, users[0])
    assert account is not None
    assert account.score == 100
    assert event.event_type == "no_show"
    assert db_session.scalar(select(func.count()).select_from(TrustEvent)) == 1


def test_rating_service_rejects_unknown_match(db_session: Session) -> None:
    with pytest.raises(MatchNotFound):
        RatingService(db_session).apply_match(uuid.uuid4(), now=AT)


def test_rating_account_is_per_format(db_session: Session) -> None:
    match, _, _ = finalize_match(db_session)
    lobby = db_session.get(Lobby, match.lobby_id)
    assert lobby is not None

    RatingService(db_session).apply_match(match.id, now=AT)

    accounts = list(db_session.scalars(select(RatingAccount)))
    assert len(accounts) == 10
    assert all(account.format_id == lobby.format_id for account in accounts)
