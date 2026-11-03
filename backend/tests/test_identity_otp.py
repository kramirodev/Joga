"""Testes do serviço de desafio OTP (SQLite em memória, sem rede)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.models import PhoneChallenge
from app.modules.identity.otp import (
    AttemptsExceeded,
    ChallengePurpose,
    ExpiredChallenge,
    HourlyLimitReached,
    InvalidChallenge,
    InvalidCode,
    OtpPolicy,
    PhoneChallengeService,
    ResendTooSoon,
)
from app.modules.identity.phone import InvalidPhoneNumber, hash_ip, hash_otp, hash_phone
from app.modules.identity.sms import RecordingSmsSender, SmsMessage

SECRET = "test-secret"
PHONE = "+5511987654321"
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


def build_service(
    session: Session,
    sender: RecordingSmsSender,
    policy: OtpPolicy | None = None,
) -> PhoneChallengeService:
    return PhoneChallengeService(session, sender, SECRET, policy)


def last_message(sender: RecordingSmsSender) -> SmsMessage:
    message = sender.last_message()
    assert message is not None
    return message


def test_request_persists_only_hashes_and_sends_code(session: Session) -> None:
    sender = RecordingSmsSender()
    service = build_service(session, sender)

    issued = service.request(
        " +55 (11) 98765-4321 ",
        ChallengePurpose.registration,
        now=BASE_TIME,
        request_ip="203.0.113.9",
    )

    message = last_message(sender)
    assert message.phone == PHONE
    assert len(message.code) == 6
    assert message.code.isdigit()

    challenge = session.get(PhoneChallenge, issued.challenge_id)
    assert challenge is not None
    assert challenge.phone_hash == hash_phone(PHONE, SECRET)
    assert challenge.code_hash == hash_otp(issued.challenge_id, message.code, SECRET)
    assert challenge.code_hash != message.code
    assert challenge.request_ip_hash == hash_ip("203.0.113.9", SECRET)
    assert challenge.purpose == "registration"
    assert challenge.attempts == 0
    assert challenge.max_attempts == 5
    assert challenge.consumed_at is None
    assert issued.expires_at == BASE_TIME + timedelta(seconds=300)
    assert PHONE not in repr(challenge.__dict__)


def test_request_rejects_non_e164_phone(session: Session) -> None:
    service = build_service(session, RecordingSmsSender())

    with pytest.raises(InvalidPhoneNumber):
        service.request("11987654321", ChallengePurpose.login, now=BASE_TIME)


def test_request_enforces_resend_cooldown(session: Session) -> None:
    service = build_service(session, RecordingSmsSender())

    service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)

    with pytest.raises(ResendTooSoon) as error:
        service.request(
            PHONE,
            ChallengePurpose.login,
            now=BASE_TIME + timedelta(seconds=30),
        )
    assert error.value.retry_after_seconds == 30

    service.request(PHONE, ChallengePurpose.login, now=BASE_TIME + timedelta(seconds=60))


def test_request_enforces_hourly_limit(session: Session) -> None:
    service = build_service(
        session,
        RecordingSmsSender(),
        OtpPolicy(resend_cooldown_seconds=0, max_per_hour=3),
    )

    for offset in range(3):
        service.request(
            PHONE,
            ChallengePurpose.recovery,
            now=BASE_TIME + timedelta(seconds=offset),
        )

    with pytest.raises(HourlyLimitReached):
        service.request(
            PHONE,
            ChallengePurpose.recovery,
            now=BASE_TIME + timedelta(seconds=3),
        )


def test_verify_consumes_challenge_and_blocks_replay(session: Session) -> None:
    sender = RecordingSmsSender()
    service = build_service(session, sender)
    issued = service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)
    code = last_message(sender).code

    session.expire_all()

    verified = service.verify(
        issued.challenge_id, f" {code} ", now=BASE_TIME + timedelta(seconds=10)
    )

    assert verified.phone_hash == hash_phone(PHONE, SECRET)
    assert verified.purpose is ChallengePurpose.login
    assert verified.user_id is None

    challenge = session.get(PhoneChallenge, issued.challenge_id)
    assert challenge is not None
    assert challenge.consumed_at is not None

    with pytest.raises(InvalidChallenge):
        service.verify(issued.challenge_id, code, now=BASE_TIME + timedelta(seconds=11))


def test_verify_counts_wrong_codes_and_locks(session: Session) -> None:
    sender = RecordingSmsSender()
    service = build_service(session, sender)
    issued = service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)
    code = last_message(sender).code
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(4):
        with pytest.raises(InvalidCode):
            service.verify(issued.challenge_id, wrong, now=BASE_TIME)

    challenge = session.get(PhoneChallenge, issued.challenge_id)
    assert challenge is not None
    assert challenge.attempts == 4

    with pytest.raises(AttemptsExceeded):
        service.verify(issued.challenge_id, wrong, now=BASE_TIME)

    with pytest.raises(AttemptsExceeded):
        service.verify(issued.challenge_id, code, now=BASE_TIME)


def test_verify_rejects_expired_challenge(session: Session) -> None:
    sender = RecordingSmsSender()
    service = build_service(session, sender)
    issued = service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)
    code = last_message(sender).code

    with pytest.raises(ExpiredChallenge):
        service.verify(
            issued.challenge_id,
            code,
            now=BASE_TIME + timedelta(seconds=300),
        )


def test_verify_rejects_unknown_challenge(session: Session) -> None:
    service = build_service(session, RecordingSmsSender())

    with pytest.raises(InvalidChallenge):
        service.verify(uuid.uuid4(), "123456", now=BASE_TIME)


def test_fixed_code_is_used_for_local_development(session: Session) -> None:
    sender = RecordingSmsSender()
    service = PhoneChallengeService(
        session,
        sender,
        SECRET,
        OtpPolicy(fixed_code="123456"),
    )
    issued = service.request(PHONE, ChallengePurpose.login, now=BASE_TIME)

    assert last_message(sender).code == "123456"
    verified = service.verify(issued.challenge_id, "123456", now=BASE_TIME + timedelta(seconds=1))
    assert verified.phone_hash == hash_phone(PHONE, SECRET)
