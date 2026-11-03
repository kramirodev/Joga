"""Testes da troca de telefone autenticada."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_challenge_service, get_sms_sender
from app.core.config import DEFAULT_PHONE_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.events import (
    AUTH_PHONE_CHANGE_COMPLETED,
    AUTH_PHONE_CHANGE_REQUESTED,
)
from app.modules.identity.models import PhoneChallenge, SecurityEvent, UserPhone
from app.modules.identity.otp import OtpPolicy, PhoneChallengeService
from app.modules.identity.phone import hash_phone
from app.modules.identity.sms import RecordingSmsSender

PHONE_A = "+5511987654321"
PHONE_B = "+5511911112222"
PHONE_C = "+5511933334444"


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
    client.app.dependency_overrides[get_challenge_service] = lambda: PhoneChallengeService(
        db_session,
        sms_sender,
        DEFAULT_PHONE_HASH_SECRET,
        OtpPolicy(resend_cooldown_seconds=0),
    )
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def request_challenge(api: TestClient, phone: str, purpose: str) -> Response:
    return api.post(
        "/api/v1/auth/phone/challenges",
        json={"phone": phone, "purpose": purpose},
    )


def verify(api: TestClient, challenge_id: str, code: str) -> Response:
    return api.post(
        f"/api/v1/auth/phone/challenges/{challenge_id}/verify",
        json={"code": code},
    )


def register_user(
    api: TestClient,
    sender: RecordingSmsSender,
    phone: str,
) -> dict[str, str]:
    challenge = request_challenge(api, phone, "registration")
    assert challenge.status_code == 202, challenge.text
    message = sender.last_message()
    assert message is not None
    verified = verify(api, challenge.json()["challenge_id"], message.code)
    assert verified.status_code == 200, verified.text
    registered = api.post(
        "/api/v1/auth/registration",
        json={"challenge_id": verified.json()["challenge_id"]},
    )
    assert registered.status_code == 201, registered.text
    return registered.json()


def request_phone_change(
    api: TestClient,
    access_token: str,
    new_phone: str,
) -> Response:
    return api.post(
        "/api/v1/auth/phone-change/challenges",
        json={"new_phone": new_phone},
        headers=bearer(access_token),
    )


def confirm_phone_change(
    api: TestClient,
    access_token: str,
    challenge_id: str,
    code: str,
) -> Response:
    return api.post(
        "/api/v1/auth/phone-change",
        json={"challenge_id": challenge_id, "code": code},
        headers=bearer(access_token),
    )


def test_phone_change_requires_authentication(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/phone-change/challenges",
        json={"new_phone": PHONE_B},
    )

    assert response.status_code == 401


def test_phone_change_request_creates_bound_challenge(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens = register_user(api, sms_sender, PHONE_A)

    response = request_phone_change(api, tokens["access_token"], PHONE_B)

    assert response.status_code == 202, response.text
    body = response.json()
    assert PHONE_A not in response.text
    assert PHONE_B not in response.text
    challenge = db_session.get(PhoneChallenge, UUID(body["challenge_id"]))
    assert challenge is not None
    assert challenge.purpose == "phone_change"
    assert challenge.user_id is not None
    message = sms_sender.last_message()
    assert message is not None
    assert message.phone == PHONE_B


def test_phone_change_rejects_same_phone(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens = register_user(api, sms_sender, PHONE_A)

    response = request_phone_change(api, tokens["access_token"], PHONE_A)

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "phone_unchanged"}}


def test_phone_change_rejects_phone_from_other_account(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens_a = register_user(api, sms_sender, PHONE_A)
    register_user(api, sms_sender, PHONE_B)

    response = request_phone_change(api, tokens_a["access_token"], PHONE_B)

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "phone_already_registered"}}


def test_confirm_changes_phone_and_revokes_sessions(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens = register_user(api, sms_sender, PHONE_A)
    access = tokens["access_token"]
    requested = request_phone_change(api, access, PHONE_B)
    assert requested.status_code == 202
    challenge_id = requested.json()["challenge_id"]
    message = sms_sender.last_message()
    assert message is not None

    response = confirm_phone_change(api, access, challenge_id, message.code)

    assert response.status_code == 204
    assert api.get("/api/v1/auth/me", headers=bearer(access)).status_code == 401

    phones = list(db_session.scalars(select(UserPhone).where(UserPhone.released_at.is_(None))))
    assert len(phones) == 1
    assert phones[0].phone_hash == hash_phone(PHONE_B, DEFAULT_PHONE_HASH_SECRET)
    old_phone = db_session.scalar(
        select(UserPhone).where(
            UserPhone.phone_hash == hash_phone(PHONE_A, DEFAULT_PHONE_HASH_SECRET)
        )
    )
    assert old_phone is not None and old_phone.released_at is not None
    challenge = db_session.get(PhoneChallenge, UUID(challenge_id))
    assert challenge is not None and challenge.receipt_used_at is not None

    login_challenge = request_challenge(api, PHONE_B, "login")
    assert login_challenge.status_code == 202
    login_message = sms_sender.last_message()
    assert login_message is not None
    verified = verify(api, login_challenge.json()["challenge_id"], login_message.code)
    logged_in = api.post(
        "/api/v1/auth/login",
        json={"challenge_id": verified.json()["challenge_id"]},
    )
    assert logged_in.status_code == 200

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert AUTH_PHONE_CHANGE_REQUESTED in event_types
    assert AUTH_PHONE_CHANGE_COMPLETED in event_types


def test_wrong_code_keeps_phone_and_allows_retry(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens = register_user(api, sms_sender, PHONE_A)
    access = tokens["access_token"]
    requested = request_phone_change(api, access, PHONE_B)
    challenge_id = requested.json()["challenge_id"]
    message = sms_sender.last_message()
    assert message is not None
    wrong = "000000" if message.code != "000000" else "111111"

    failed = confirm_phone_change(api, access, challenge_id, wrong)
    assert failed.status_code == 400
    assert failed.json() == {"detail": {"code": "invalid_phone_change"}}

    challenge = db_session.get(PhoneChallenge, UUID(challenge_id))
    assert challenge is not None
    assert challenge.consumed_at is None
    assert challenge.attempts == 1

    retried = confirm_phone_change(api, access, challenge_id, message.code)
    assert retried.status_code == 204


def test_other_user_cannot_confirm_phone_change(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    tokens_a = register_user(api, sms_sender, PHONE_A)
    tokens_b = register_user(api, sms_sender, PHONE_B)
    requested = request_phone_change(api, tokens_a["access_token"], PHONE_C)
    challenge_id = requested.json()["challenge_id"]
    message = sms_sender.last_message()
    assert message is not None

    response = confirm_phone_change(
        api,
        tokens_b["access_token"],
        challenge_id,
        message.code,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_phone_change"}}
    challenge = db_session.get(PhoneChallenge, UUID(challenge_id))
    assert challenge is not None
    assert challenge.consumed_at is None
    assert challenge.receipt_used_at is None


def test_public_challenge_endpoint_rejects_phone_change_purpose(api: TestClient) -> None:
    response = request_challenge(api, PHONE_A, "phone_change")

    assert response.status_code == 422
