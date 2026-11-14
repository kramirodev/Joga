"""Fechamento de temporada e reset suave da divisão (Fase 14D.14)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ratings.engine import division_progress
from app.modules.ratings.models import RatingAccount
from app.modules.ratings.service import RatingService
from app.modules.season.models import Season, SeasonTrackLevel
from app.modules.season.service import close_expired_season
from tests.test_ratings_service import AT, finalize_match


def season_by_code(session: Session, code: str) -> Season | None:
    return session.scalars(select(Season).where(Season.code == code)).first()


def test_close_season_opens_next_and_keeps_rating(db_session: Session) -> None:
    match, users, _ = finalize_match(db_session)
    result = RatingService(db_session).apply_match(match.id, now=AT)
    assert result.applied == 10

    service = RatingService(db_session)
    current = service.current_season(AT)
    assert current is not None
    assert current.code == "2026-Q4"
    assert service.placement_matches(users[0], current.id) == 1

    following = close_expired_season(db_session, now=datetime(2027, 1, 1, 0, 5, tzinfo=UTC))
    assert following is not None
    assert following.code == "2027-Q1"
    assert following.status == "active"
    closed = season_by_code(db_session, "2026-Q4")
    assert closed is not None and closed.status == "closed"

    account = db_session.scalars(
        select(RatingAccount).where(RatingAccount.user_id == users[0])
    ).first()
    assert account is not None
    assert account.matches_played == 1

    assert service.placement_matches(users[0], following.id) == 0
    progress = division_progress(account.rating, 0)
    assert progress["provisional"] is True
    assert progress["placement_matches_remaining"] == 5


def test_closing_without_expired_season_is_noop(db_session: Session) -> None:
    assert close_expired_season(db_session, now=AT) is None
    season = season_by_code(db_session, "2026-Q4")
    assert season is not None and season.status == "active"


def test_next_season_has_its_own_track(db_session: Session) -> None:
    following = close_expired_season(db_session, now=datetime(2027, 1, 1, 0, 5, tzinfo=UTC))
    assert following is not None
    levels = db_session.scalars(
        select(SeasonTrackLevel).where(SeasonTrackLevel.season_id == following.id)
    ).all()
    assert len(levels) == 30
