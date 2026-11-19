"""Concorrência do índice único de e-mail contra PostgreSQL real.

Executado apenas quando `JOGA_TEST_DATABASE_URL` aponta para um banco
descartável. Usa schema isolado para não tocar nas tabelas da migração.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.email.deliveries import EmailDeliveryService
from app.modules.email.drain_lock import email_drain_lock
from app.modules.email.models import UserEmail
from app.modules.identity.email_accounts import (
    EmailAccountService,
    EmailAlreadyRegistered,
)
from app.modules.identity.email_challenges import EmailChallengeService
from app.modules.identity.models import User
from app.modules.identity.otp import ChallengePurpose, OtpPolicy
from app.modules.identity.passwords import PasswordService

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "email_test"
SECRET = "postgres-email-secret"
EMAIL = "concorrente@example.com"
BASE_TIME = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

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
def clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def _service(session: Session) -> EmailAccountService:
    deliveries = EmailDeliveryService(
        session,
        provider="fake",
        daily_budget=1_000,
        secret=SECRET,
    )
    challenges = EmailChallengeService(
        session,
        deliveries,
        SECRET,
        OtpPolicy(fixed_code="123456", resend_cooldown_seconds=0),
    )
    hasher = PasswordHasher(memory_cost=1024, time_cost=1, parallelism=1)
    passwords = PasswordService(
        hasher,
        dummy_hash=hasher.hash("dummy-password-not-used"),
    )
    return EmailAccountService(session, challenges, deliveries, passwords, SECRET)


def _consumed_challenge(session: Session, suffix: str) -> str:
    service = _service(session)
    issued = service._challenges.request(  # noqa: SLF001 - monta recibo real
        EMAIL,
        ChallengePurpose.email_verification,
        now=BASE_TIME + timedelta(seconds=int(suffix)),
        suppress_delivery=True,
    )
    service._challenges.verify(  # noqa: SLF001
        issued.challenge_id,
        "123456",
        now=BASE_TIME + timedelta(seconds=int(suffix) + 1),
    )
    return str(issued.challenge_id)


def test_advisory_lock_blocks_a_second_drainer(engine: Engine) -> None:
    with email_drain_lock(engine) as first:
        assert first is True
        with email_drain_lock(engine) as second:
            assert second is False
    with email_drain_lock(engine) as released:
        assert released is True


def test_partial_unique_index_blocks_duplicate_active_email(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(
            UserEmail(
                user_id=user.id,
                email_normalized=EMAIL,
                is_primary=True,
            )
        )
        session.flush()

        other = User(status="active")
        session.add(other)
        session.flush()
        session.add(
            UserEmail(
                user_id=other.id,
                email_normalized=EMAIL,
                is_primary=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_only_one_active_primary_per_user(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(
            UserEmail(
                user_id=user.id,
                email_normalized="um@example.com",
                is_primary=True,
            )
        )
        session.flush()
        session.add(
            UserEmail(
                user_id=user.id,
                email_normalized="dois@example.com",
                is_primary=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_concurrent_registration_allows_only_one_winner(
    session_factory: sessionmaker[Session],
) -> None:
    challenge_ids: list[str] = []
    with session_factory() as session:
        challenge_ids.append(_consumed_challenge(session, "1"))
        challenge_ids.append(_consumed_challenge(session, "2"))
        session.commit()

    barrier = threading.Barrier(2)

    def register_once(challenge_id: str) -> str:
        import uuid

        with session_factory() as session:
            barrier.wait()
            try:
                _service(session).register(
                    uuid.UUID(challenge_id),
                    EMAIL,
                    "SenhaSeguraBeta123",
                    now=BASE_TIME,
                )
                session.commit()
                return "ok"
            except EmailAlreadyRegistered:
                session.rollback()
                return "email_already_registered"
            except IntegrityError:
                session.rollback()
                return "integrity_error"
            except Exception as error:  # noqa: BLE001 - o teste identifica falhas
                session.rollback()
                return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(register_once, challenge_ids))

    assert results.count("ok") == 1
    assert sorted(results) in (
        ["email_already_registered", "ok"],
        ["integrity_error", "ok"],
    )

    with session_factory() as session:
        from sqlalchemy import func, select

        assert session.scalar(select(func.count()).select_from(UserEmail)) == 1
        assert session.scalar(select(func.count()).select_from(User)) == 1
