"""Testes das constraints básicas do modelo de identidade."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.models import (
    PasskeyCredential,
    User,
    UserPhone,
)
from app.modules.identity.models import (
    Session as AuthSession,
)

PHONE_HASH = "a" * 64
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


def make_user(session: Session, status: str = "active") -> User:
    user = User(status=status)
    session.add(user)
    session.flush()
    return user


def test_user_rejects_unknown_status(session: Session) -> None:
    with pytest.raises(IntegrityError):
        make_user(session, status="unknown")
    session.rollback()


def test_active_phone_hash_is_unique(session: Session) -> None:
    user = make_user(session)
    session.add(UserPhone(user_id=user.id, phone_hash=PHONE_HASH, is_primary=True))
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(UserPhone(user_id=user.id, phone_hash=PHONE_HASH, is_primary=False))
        session.flush()
    session.rollback()


def test_released_phone_hash_can_be_reused(session: Session) -> None:
    user = make_user(session)
    session.add(
        UserPhone(
            user_id=user.id,
            phone_hash=PHONE_HASH,
            is_primary=False,
            released_at=BASE_TIME,
        )
    )
    session.add(UserPhone(user_id=user.id, phone_hash=PHONE_HASH, is_primary=True))
    session.flush()


def test_credential_id_is_unique(session: Session) -> None:
    user = make_user(session)
    for _ in range(2):
        session.add(
            PasskeyCredential(
                user_id=user.id,
                credential_id="credential-1",
                public_key=b"public-key",
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_refresh_token_hash_is_unique(session: Session) -> None:
    user = make_user(session)
    for index in range(2):
        session.add(
            AuthSession(
                user_id=user.id,
                family_id=uuid.uuid4(),
                access_token_hash=f"a{index}" * 32,
                access_expires_at=BASE_TIME + timedelta(minutes=10),
                refresh_token_hash="b" * 64,
                expires_at=BASE_TIME + timedelta(days=30),
                idle_expires_at=BASE_TIME + timedelta(days=7),
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
