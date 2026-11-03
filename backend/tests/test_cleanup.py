"""Testes da limpeza de desafios, sessões e eventos antigos."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.cleanup import cleanup_identity
from app.modules.identity.models import (
    PasskeyChallenge,
    PhoneChallenge,
    SecurityEvent,
    User,
)
from app.modules.identity.models import Session as SessionRecord

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


def count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def make_session_row(
    session: Session,
    user_id: uuid.UUID,
    *,
    expires_at: datetime,
    suffix: str,
) -> None:
    session.add(
        SessionRecord(
            user_id=user_id,
            family_id=uuid.uuid4(),
            access_token_hash=(f"a{suffix}" * 32)[:64],
            access_expires_at=BASE_TIME,
            refresh_token_hash=(f"b{suffix}" * 32)[:64],
            expires_at=expires_at,
            idle_expires_at=expires_at,
        )
    )


def test_cleanup_removes_only_old_rows(session: Session) -> None:
    user = User(status="active")
    session.add(user)
    session.flush()

    for suffix, expires in (
        ("old", BASE_TIME - timedelta(days=2)),
        ("new", BASE_TIME + timedelta(hours=1)),
    ):
        session.add(
            PhoneChallenge(
                phone_hash=f"{suffix:0<64}"[:64],
                purpose="login",
                code_hash="c" * 64,
                attempts=0,
                max_attempts=5,
                expires_at=expires,
                created_at=BASE_TIME,
            )
        )
        session.add(
            PasskeyChallenge(
                user_id=user.id,
                challenge=f"challenge-{suffix}",
                purpose="authentication",
                expires_at=expires,
                created_at=BASE_TIME,
            )
        )

    make_session_row(
        session,
        user.id,
        expires_at=BASE_TIME - timedelta(days=31),
        suffix="x",
    )
    make_session_row(
        session,
        user.id,
        expires_at=BASE_TIME + timedelta(days=30),
        suffix="y",
    )
    session.add(
        SecurityEvent(
            user_id=user.id,
            event_type="old",
            created_at=BASE_TIME - timedelta(days=91),
        )
    )
    session.add(
        SecurityEvent(
            user_id=user.id,
            event_type="new",
            created_at=BASE_TIME - timedelta(hours=1),
        )
    )
    session.flush()

    result = cleanup_identity(session, now=BASE_TIME)

    assert result.phone_challenges == 1
    assert result.passkey_challenges == 1
    assert result.sessions == 1
    assert result.security_events == 1
    assert count(session, PhoneChallenge) == 1
    assert count(session, PasskeyChallenge) == 1
    assert count(session, SessionRecord) == 1
    assert count(session, SecurityEvent) == 1
