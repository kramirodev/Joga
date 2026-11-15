"""Testes do fluxo completo de conta e sessão (SQLite em memória)."""

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
    AUTH_LOGIN_COMPLETED,
    AUTH_LOGOUT,
    AUTH_LOGOUT_ALL,
    AUTH_REFRESH_ROTATED,
    AUTH_REGISTRATION_COMPLETED,
)
from app.modules.identity.models import PhoneChallenge, SecurityEvent, User, UserPhone
from app.modules.identity.otp import OtpPolicy, PhoneChallengeService
from app.modules.identity.sms import RecordingSmsSender

PHONE = "+5511987654321"
OTHER_PHONE = "+5511911112222"


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


def receipt_for(
    api: TestClient,
    sender: RecordingSmsSender,
    phone: str,
    purpose: str,
) -> str:
    created = request_challenge(api, phone, purpose)
    assert created.status_code == 202, created.text
    message = sender.last_message()
    assert message is not None
    verified = verify(api, created.json()["challenge_id"], message.code)
    assert verified.status_code == 200, verified.text
    return verified.json()["challenge_id"]


def register(api: TestClient, receipt: str) -> Response:
    return api.post("/api/v1/auth/registration", json={"challenge_id": receipt})


def login(api: TestClient, receipt: str) -> Response:
    return api.post("/api/v1/auth/login", json={"challenge_id": receipt})


def refresh(api: TestClient, token: str) -> Response:
    return api.post("/api/v1/auth/refresh", json={"refresh_token": token})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_tokens_and_me_works(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")

    response = register(api, receipt)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["status"] == "active"
    assert PHONE not in response.text

    user_id = UUID(body["user"]["id"])
    assert db_session.get(User, user_id) is not None
    phone = db_session.scalar(select(UserPhone).where(UserPhone.user_id == user_id))
    assert phone is not None and phone.verified_at is not None
    challenge = db_session.get(PhoneChallenge, UUID(receipt))
    assert challenge is not None and challenge.receipt_used_at is not None

    me = api.get("/api/v1/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == str(user_id)

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert AUTH_REGISTRATION_COMPLETED in event_types


def test_register_rejects_replayed_receipt(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    assert register(api, receipt).status_code == 201

    replay = register(api, receipt)

    assert replay.status_code == 400
    assert replay.json() == {"detail": {"code": "invalid_receipt"}}


def test_register_rejects_phone_with_existing_account(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    first = receipt_for(api, sms_sender, PHONE, "registration")
    assert register(api, first).status_code == 201

    second = receipt_for(api, sms_sender, PHONE, "registration")
    response = register(api, second)

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "phone_already_registered"}}


def test_login_returns_session_for_existing_account(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    registration = receipt_for(api, sms_sender, PHONE, "registration")
    assert register(api, registration).status_code == 201

    login_receipt = receipt_for(api, sms_sender, PHONE, "login")
    response = login(api, login_receipt)

    assert response.status_code == 200, response.text
    me = api.get("/api/v1/auth/me", headers=bearer(response.json()["access_token"]))
    assert me.status_code == 200


def test_login_unknown_phone_returns_not_found(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, OTHER_PHONE, "login")

    response = login(api, receipt)

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "account_not_found"}}


def test_me_rejects_missing_or_invalid_token(api: TestClient) -> None:
    assert api.get("/api/v1/auth/me").status_code == 401

    response = api.get("/api/v1/auth/me", headers=bearer("invalid-token"))

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"detail": {"code": "invalid_token"}}


def test_refresh_rotation_and_reuse(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    first = register(api, receipt).json()

    rotated = refresh(api, first["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()

    assert api.get("/api/v1/auth/me", headers=bearer(first["access_token"])).status_code == 401
    assert api.get("/api/v1/auth/me", headers=bearer(second["access_token"])).status_code == 200

    reuse = refresh(api, first["refresh_token"])
    assert reuse.status_code == 401
    assert reuse.json() == {"detail": {"code": "refresh_reuse_detected"}}

    assert api.get("/api/v1/auth/me", headers=bearer(second["access_token"])).status_code == 401
    assert refresh(api, second["refresh_token"]).status_code == 401

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert AUTH_REFRESH_ROTATED in event_types


def test_logout_revokes_current_session(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    tokens = register(api, receipt).json()

    logout = api.post("/api/v1/auth/logout", headers=bearer(tokens["access_token"]))

    assert logout.status_code == 204
    assert api.get("/api/v1/auth/me", headers=bearer(tokens["access_token"])).status_code == 401
    refresh_response = refresh(api, tokens["refresh_token"])
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {"detail": {"code": "invalid_refresh_token"}}


def test_logout_all_revokes_every_session(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    registration = receipt_for(api, sms_sender, PHONE, "registration")
    first = register(api, registration).json()
    login_receipt = receipt_for(api, sms_sender, PHONE, "login")
    second = login(api, login_receipt).json()

    response = api.post("/api/v1/auth/logout-all", headers=bearer(first["access_token"]))

    assert response.status_code == 204
    for tokens in (first, second):
        assert api.get("/api/v1/auth/me", headers=bearer(tokens["access_token"])).status_code == 401
        assert refresh(api, tokens["refresh_token"]).status_code == 401

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert AUTH_LOGOUT_ALL in event_types
    assert AUTH_LOGIN_COMPLETED in event_types


def test_security_events_do_not_store_tokens(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    tokens = register(api, receipt).json()
    api.post("/api/v1/auth/logout", headers=bearer(tokens["access_token"]))

    events = list(db_session.scalars(select(SecurityEvent)))
    serialized = " ".join(str(event.details) for event in events)
    assert tokens["access_token"] not in serialized
    assert tokens["refresh_token"] not in serialized
    assert any(event.event_type == AUTH_LOGOUT for event in events)
