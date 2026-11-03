"""Testes do consumo de recibo para cadastro e login."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.accounts import (
    AccountNotFound,
    AccountService,
    InvalidReceipt,
    PhoneAlreadyRegistered,
)
from app.modules.identity.models import PhoneChallenge, User, UserPhone
from app.modules.identity.otp import ChallengePurpose

BASE_TIME = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
PHONE_HASH = "f" * 64


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


def make_receipt(
    session: Session,
    *,
    purpose: ChallengePurpose = ChallengePurpose.registration,
    consumed_at: datetime | None = None,
    receipt_used_at: datetime | None = None,
    phone_hash: str = PHONE_HASH,
) -> uuid.UUID:
    challenge_id = uuid.uuid4()
    consumed = consumed_at or BASE_TIME
    session.add(
        PhoneChallenge(
            id=challenge_id,
            phone_hash=phone_hash,
            purpose=purpose.value,
            code_hash="a" * 64,
            attempts=1,
            max_attempts=5,
            expires_at=consumed + timedelta(minutes=5),
            consumed_at=consumed,
            receipt_used_at=receipt_used_at,
            created_at=consumed - timedelta(minutes=1),
        )
    )
    session.flush()
    return challenge_id


def build_service(session: Session) -> AccountService:
    return AccountService(session, receipt_ttl_seconds=600)


def test_register_creates_user_and_verified_phone(session: Session) -> None:
    challenge_id = make_receipt(session)
    service = build_service(session)

    user = service.register(challenge_id, now=BASE_TIME + timedelta(seconds=10))

    row = session.get(User, user.id)
    assert row is not None and row.status == "active"
    phone = session.scalar(select(UserPhone).where(UserPhone.user_id == user.id))
    assert phone is not None
    assert phone.phone_hash == PHONE_HASH
    assert phone.verified_at is not None
    challenge = session.get(PhoneChallenge, challenge_id)
    assert challenge is not None
    assert challenge.receipt_used_at is not None


def test_register_rejects_replayed_receipt(session: Session) -> None:
    challenge_id = make_receipt(session)
    service = build_service(session)
    service.register(challenge_id, now=BASE_TIME)

    with pytest.raises(InvalidReceipt):
        service.register(challenge_id, now=BASE_TIME + timedelta(seconds=10))


def test_register_rejects_expired_receipt(session: Session) -> None:
    challenge_id = make_receipt(session)
    service = build_service(session)

    with pytest.raises(InvalidReceipt):
        service.register(challenge_id, now=BASE_TIME + timedelta(seconds=601))


def test_register_rejects_wrong_purpose(session: Session) -> None:
    challenge_id = make_receipt(session, purpose=ChallengePurpose.login)

    with pytest.raises(InvalidReceipt):
        build_service(session).register(challenge_id, now=BASE_TIME)


def test_register_rejects_phone_with_active_account(session: Session) -> None:
    existing_user = User(status="active")
    session.add(existing_user)
    session.flush()
    session.add(UserPhone(user_id=existing_user.id, phone_hash=PHONE_HASH, is_primary=True))
    session.flush()
    challenge_id = make_receipt(session)

    with pytest.raises(PhoneAlreadyRegistered):
        build_service(session).register(challenge_id, now=BASE_TIME)


def test_login_returns_existing_active_account(session: Session) -> None:
    user = User(status="active")
    session.add(user)
    session.flush()
    session.add(UserPhone(user_id=user.id, phone_hash=PHONE_HASH, is_primary=True))
    session.flush()
    challenge_id = make_receipt(session, purpose=ChallengePurpose.login)

    authenticated = build_service(session).login(challenge_id, now=BASE_TIME)

    assert authenticated.id == user.id
    challenge = session.get(PhoneChallenge, challenge_id)
    assert challenge is not None and challenge.receipt_used_at is not None


def test_login_unknown_phone_returns_account_not_found(session: Session) -> None:
    challenge_id = make_receipt(session, purpose=ChallengePurpose.login)

    with pytest.raises(AccountNotFound):
        build_service(session).login(challenge_id, now=BASE_TIME)


def test_login_rejects_registration_receipt(session: Session) -> None:
    challenge_id = make_receipt(session, purpose=ChallengePurpose.registration)

    with pytest.raises(InvalidReceipt):
        build_service(session).login(challenge_id, now=BASE_TIME)
