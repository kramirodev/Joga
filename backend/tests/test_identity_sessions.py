"""Testes do serviço de sessões (SQLite em memória)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.clock import ensure_utc
from app.modules.identity.models import Session as SessionRecord
from app.modules.identity.models import User
from app.modules.identity.sessions import (
    InvalidAccessToken,
    InvalidRefreshToken,
    RefreshReuseDetected,
    SessionError,
    SessionService,
)
from app.modules.identity.tokens import hash_token

SECRET = "session-test-secret"
BASE_TIME = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_user(session: Session) -> User:
    user = User(status="active")
    session.add(user)
    session.flush()
    return user


def build_service(session: Session) -> SessionService:
    return SessionService(
        session,
        SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    )


def test_issue_persists_only_hashes(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)

    issued = service.issue(user.id, now=BASE_TIME)

    row = session.get(SessionRecord, issued.session_id)
    assert row is not None
    assert row.access_token_hash == hash_token(issued.access_token, SECRET, "access")
    assert row.refresh_token_hash == hash_token(issued.refresh_token, SECRET, "refresh")
    assert issued.access_token not in row.access_token_hash
    assert issued.refresh_token not in row.refresh_token_hash
    assert ensure_utc(row.access_expires_at) == BASE_TIME + timedelta(minutes=10)
    assert ensure_utc(row.expires_at) == BASE_TIME + timedelta(days=30)
    assert ensure_utc(row.idle_expires_at) == BASE_TIME + timedelta(days=7)


def test_authenticate_rejects_tampered_expired_and_revoked(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)

    authenticated = service.authenticate(issued.access_token, now=BASE_TIME + timedelta(seconds=1))
    assert authenticated.user_id == user.id
    assert authenticated.session_id == issued.session_id

    with pytest.raises(InvalidAccessToken):
        service.authenticate("tampered", now=BASE_TIME)

    with pytest.raises(InvalidAccessToken):
        service.authenticate(issued.access_token, now=BASE_TIME + timedelta(seconds=601))

    service.revoke_session(issued.session_id, now=BASE_TIME + timedelta(seconds=2))
    with pytest.raises(InvalidAccessToken):
        service.authenticate(issued.access_token, now=BASE_TIME + timedelta(seconds=3))


def test_rotation_invalidates_old_tokens(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)

    rotated = service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=1))

    old = session.get(SessionRecord, issued.session_id)
    assert old is not None
    assert old.revoked_reason == "rotated"
    assert old.replaced_by_session_id == rotated.session_id
    assert rotated.session_id != issued.session_id
    assert service.authenticate(rotated.access_token, now=BASE_TIME + timedelta(seconds=2))

    with pytest.raises(InvalidAccessToken):
        service.authenticate(issued.access_token, now=BASE_TIME + timedelta(seconds=2))


def test_refresh_reuse_revokes_family(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)
    rotated = service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=1))

    with pytest.raises(RefreshReuseDetected):
        service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=2))

    rotated_row = session.get(SessionRecord, rotated.session_id)
    assert rotated_row is not None
    assert rotated_row.revoked_reason == "refresh_reuse"
    with pytest.raises(InvalidAccessToken):
        service.authenticate(rotated.access_token, now=BASE_TIME + timedelta(seconds=3))


def test_refresh_absolute_expiry(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)

    with pytest.raises(InvalidRefreshToken):
        service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(days=31))

    row = session.get(SessionRecord, issued.session_id)
    assert row is not None
    assert row.revoked_reason == "expired"


def test_refresh_idle_expiry(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)

    with pytest.raises(InvalidRefreshToken):
        service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(days=8))


def test_revoke_all_revokes_every_session(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    first = service.issue(user.id, now=BASE_TIME)
    second = service.issue(user.id, now=BASE_TIME)

    count = service.revoke_all(user.id, now=BASE_TIME + timedelta(seconds=1))

    assert count == 2
    for issued in (first, second):
        with pytest.raises(InvalidAccessToken):
            service.authenticate(issued.access_token, now=BASE_TIME + timedelta(seconds=2))
        with pytest.raises(SessionError):
            service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=2))


def test_rotated_session_matches_same_family(session: Session) -> None:
    user = make_user(session)
    service = build_service(session)
    issued = service.issue(user.id, now=BASE_TIME)
    rotated = service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=1))

    old = session.get(SessionRecord, issued.session_id)
    new = session.get(SessionRecord, rotated.session_id)
    assert old is not None and new is not None
    assert old.family_id == new.family_id
