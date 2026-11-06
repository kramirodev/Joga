"""Testes do rate limiting persistente por janela fixa."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ratelimit.models import RateLimitCounter
from app.modules.ratelimit.service import (
    RateLimitExceeded,
    enforce,
    window_start_for,
)

FIXED = datetime(2026, 11, 6, 21, 0, 5, tzinfo=UTC)


def test_allows_limit_and_blocks_next(db_session: Session) -> None:
    for _ in range(3):
        enforce(db_session, scope="test", key="user-1", limit=3, now=FIXED)

    with pytest.raises(RateLimitExceeded) as error:
        enforce(db_session, scope="test", key="user-1", limit=3, now=FIXED)

    assert error.value.retry_after_seconds == 55


def test_window_resets(db_session: Session) -> None:
    for _ in range(2):
        enforce(db_session, scope="test", key="user-1", limit=2, now=FIXED)

    with pytest.raises(RateLimitExceeded):
        enforce(db_session, scope="test", key="user-1", limit=2, now=FIXED)

    enforce(
        db_session,
        scope="test",
        key="user-1",
        limit=2,
        now=FIXED + timedelta(seconds=60),
    )


def test_keys_are_isolated(db_session: Session) -> None:
    enforce(db_session, scope="test", key="user-1", limit=1, now=FIXED)
    enforce(db_session, scope="test", key="user-2", limit=1, now=FIXED)
    enforce(db_session, scope="other", key="user-1", limit=1, now=FIXED)


def test_window_start_is_aligned(db_session: Session) -> None:
    assert window_start_for(FIXED, 60) == datetime(2026, 11, 6, 21, 0, tzinfo=UTC)
    assert window_start_for(FIXED, 300) == datetime(2026, 11, 6, 21, 0, tzinfo=UTC)


def test_counter_rows_are_per_window(db_session: Session) -> None:
    enforce(db_session, scope="test", key="user-1", limit=5, now=FIXED)
    enforce(
        db_session,
        scope="test",
        key="user-1",
        limit=5,
        now=FIXED + timedelta(seconds=60),
    )

    rows = db_session.scalar(
        select(func.count()).select_from(RateLimitCounter).where(RateLimitCounter.key == "user-1")
    )
    assert rows == 2


def test_invalid_parameters_are_rejected(db_session: Session) -> None:
    with pytest.raises(ValueError):
        enforce(db_session, scope="test", key="user-1", limit=0, now=FIXED)
    with pytest.raises(ValueError):
        enforce(
            db_session,
            scope="test",
            key="user-1",
            limit=1,
            window_seconds=0,
            now=FIXED,
        )
