"""Testes de integração do domínio de identidade contra PostgreSQL real.

Executados apenas quando `JOGA_TEST_DATABASE_URL` aponta para um banco
descartável. Usam um schema isolado (`identity_test`) para não tocar nas
tabelas criadas pela migração.
"""

import os
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User, UserPhone
from app.modules.identity.otp import (
    ChallengePurpose,
    InvalidChallenge,
    OtpPolicy,
    PhoneChallengeService,
    ResendTooSoon,
)
from app.modules.identity.phone import hash_phone
from app.modules.identity.sessions import RefreshReuseDetected, SessionService
from app.modules.identity.sms import RecordingSmsSender

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "identity_test"
SECRET = "postgres-test-secret"
TOKEN_SECRET = "postgres-token-secret"
PHONE = "+5511987654321"
BASE_TIME = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de integração ignorado",
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None

    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin_engine.dispose()

    database_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    ).execution_options(schema_translate_map={None: SCHEMA})
    Base.metadata.create_all(database_engine)
    yield database_engine

    Base.metadata.drop_all(database_engine)
    database_engine.dispose()

    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_identity_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def test_partial_unique_index_blocks_duplicate_active_phone(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(UserPhone(user_id=user.id, phone_hash="c" * 64, is_primary=True))
        session.flush()

        session.add(UserPhone(user_id=user.id, phone_hash="c" * 64, is_primary=False))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_concurrent_verification_allows_only_one_success(
    session_factory: sessionmaker[Session],
) -> None:
    sender = RecordingSmsSender()
    with session_factory() as session:
        service = PhoneChallengeService(session, sender, SECRET, OtpPolicy())
        issued = service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)
        sender_message = sender.last_message()
        assert sender_message is not None
        code = sender_message.code
        session.commit()

    barrier = threading.Barrier(2)

    def verify_once() -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                service = PhoneChallengeService(session, sender, SECRET, OtpPolicy())
                service.verify(issued.challenge_id, code, now=BASE_TIME + timedelta(seconds=10))
                session.commit()
                return "ok"
            except InvalidChallenge:
                session.rollback()
                return "invalid"
            except Exception as error:  # noqa: BLE001 - o teste precisa identificar outras falhas
                session.rollback()
                return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: verify_once(), range(2)))

    assert sorted(results) == ["invalid", "ok"]


def test_concurrent_request_allows_only_one_challenge(
    session_factory: sessionmaker[Session],
) -> None:
    sender = RecordingSmsSender()
    barrier = threading.Barrier(2)

    def request_once() -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                service = PhoneChallengeService(session, sender, SECRET, OtpPolicy())
                service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)
                session.commit()
                return "ok"
            except ResendTooSoon:
                session.rollback()
                return "resend"
            except Exception as error:  # noqa: BLE001 - o teste precisa identificar outras falhas
                session.rollback()
                return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: request_once(), range(2)))

    assert sorted(results) == ["ok", "resend"]


def test_concurrent_refresh_rotation_only_one_succeeds(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        service = SessionService(
            session,
            TOKEN_SECRET,
            access_ttl_seconds=600,
            refresh_absolute_ttl_days=30,
            refresh_idle_ttl_days=7,
        )
        issued = service.issue(user.id, now=BASE_TIME)
        session.commit()

    barrier = threading.Barrier(2)

    def rotate_once() -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                service = SessionService(
                    session,
                    TOKEN_SECRET,
                    access_ttl_seconds=600,
                    refresh_absolute_ttl_days=30,
                    refresh_idle_ttl_days=7,
                )
                service.rotate(issued.refresh_token, now=BASE_TIME + timedelta(seconds=1))
                session.commit()
                return "ok"
            except RefreshReuseDetected:
                session.commit()
                return "reuse"
            except Exception as error:  # noqa: BLE001 - o teste precisa identificar outras falhas
                session.rollback()
                return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: rotate_once(), range(2)))

    assert sorted(results) == ["ok", "reuse"]


def test_phone_hash_is_persisted_as_hmac(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(
            UserPhone(
                user_id=user.id,
                phone_hash=hash_phone(PHONE, SECRET),
                is_primary=True,
            )
        )
        session.commit()

        stored = session.scalar(select(UserPhone.phone_hash).limit(1))
        assert stored == hash_phone(PHONE, SECRET)
        assert PHONE not in stored
