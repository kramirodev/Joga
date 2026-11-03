"""Testes dos endpoints de desafio e verificação de telefone."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_challenge_service, get_sms_sender
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.events import (
    OTP_CHALLENGE_REQUESTED,
    OTP_RATE_LIMITED,
    OTP_VERIFICATION_FAILED,
)
from app.modules.identity.models import PhoneChallenge, SecurityEvent
from app.modules.identity.otp import OtpPolicy, PhoneChallengeService
from app.modules.identity.phone import hash_otp
from app.modules.identity.sms import RecordingSmsSender

PHONE = "+5511987654321"
OTHER_PHONE = "+5511911112222"
SECRET = "local-development-only-change-me"


@pytest.fixture
def api(
    client: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_sms_sender] = lambda: sms_sender
    return client


def post_challenge(
    api: TestClient,
    phone: str = PHONE,
    purpose: str = "login",
) -> Response:
    return api.post(
        "/api/v1/auth/phone/challenges",
        json={"phone": phone, "purpose": purpose},
    )


def post_verify(api: TestClient, challenge_id: str, code: str) -> Response:
    return api.post(
        f"/api/v1/auth/phone/challenges/{challenge_id}/verify",
        json={"code": code},
    )


def last_code(sender: RecordingSmsSender) -> str:
    message = sender.last_message()
    assert message is not None
    return message.code


def test_request_challenge_returns_202_without_phone(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    response = post_challenge(api, purpose="registration")

    assert response.status_code == 202
    body = response.json()
    challenge_id = UUID(body["challenge_id"])
    assert body["resend_after_seconds"] == 60
    assert PHONE not in response.text

    message = sms_sender.last_message()
    assert message is not None
    assert message.phone == PHONE
    assert len(message.code) == 6

    challenge = db_session.get(PhoneChallenge, challenge_id)
    assert challenge is not None
    assert challenge.code_hash == hash_otp(challenge_id, message.code, SECRET)
    assert challenge.code_hash != message.code

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert OTP_CHALLENGE_REQUESTED in event_types


def test_verify_returns_receipt_and_blocks_replay(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    issued = post_challenge(api).json()
    challenge_id = issued["challenge_id"]
    code = last_code(sms_sender)

    response = post_verify(api, challenge_id, code)

    assert response.status_code == 200
    body = response.json()
    assert body["challenge_id"] == challenge_id
    assert body["purpose"] == "login"
    assert body["receipt_expires_at"] > body["verified_at"]

    challenge = db_session.get(PhoneChallenge, UUID(challenge_id))
    assert challenge is not None
    assert challenge.consumed_at is not None

    replay = post_verify(api, challenge_id, code)
    assert replay.status_code == 400
    assert replay.json() == {"detail": {"code": "invalid_code_or_challenge"}}


def test_request_rejects_invalid_phone(api: TestClient) -> None:
    response = post_challenge(api, phone="11987654321")

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_phone"}}


def test_request_returns_429_during_resend_cooldown(
    api: TestClient,
    db_session: Session,
) -> None:
    assert post_challenge(api).status_code == 202

    response = post_challenge(api, purpose="login")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json() == {"detail": {"code": "rate_limited"}}

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert OTP_RATE_LIMITED in event_types


def test_verify_counts_wrong_codes_and_locks(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    issued = post_challenge(api).json()
    challenge_id = issued["challenge_id"]
    code = last_code(sms_sender)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(4):
        assert post_verify(api, challenge_id, wrong).status_code == 400

    challenge = db_session.get(PhoneChallenge, UUID(challenge_id))
    assert challenge is not None
    assert challenge.attempts == 4

    assert post_verify(api, challenge_id, wrong).status_code == 400
    assert post_verify(api, challenge_id, code).status_code == 400

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert OTP_VERIFICATION_FAILED in event_types


def test_verify_unknown_challenge_returns_generic_error(api: TestClient) -> None:
    response = post_verify(api, "00000000-0000-0000-0000-000000000000", "123456")

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_code_or_challenge"}}


def test_ip_hourly_limit_blocks_second_phone_from_same_ip(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    api.app.dependency_overrides[get_challenge_service] = lambda: PhoneChallengeService(
        db_session,
        sms_sender,
        SECRET,
        OtpPolicy(resend_cooldown_seconds=0, max_per_ip_per_hour=1),
    )

    assert post_challenge(api, phone=PHONE).status_code == 202
    response = post_challenge(api, phone=OTHER_PHONE)

    assert response.status_code == 429
    assert response.json() == {"detail": {"code": "rate_limited"}}


def test_production_without_sms_provider_returns_503(
    client: TestClient,
    db_session: Session,
) -> None:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        environment="production",
        phone_hash_secret="real-secret-outside-the-repository",
        token_hash_secret="real-token-secret-outside-the-repository",
    )

    response = post_challenge(client)

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sms_provider_unavailable"}}
