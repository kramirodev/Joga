"""Testes da sessão web do painel (cookie HttpOnly + CSRF)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_challenge_service, get_sms_sender
from app.api.v1.web_auth import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.config import DEFAULT_PHONE_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.events import AUTH_LOGOUT, AUTH_REFRESH_ROTATED
from app.modules.identity.models import SecurityEvent
from app.modules.identity.otp import OtpPolicy, PhoneChallengeService
from app.modules.identity.sms import RecordingSmsSender

PHONE = "+5511987654321"


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


def web_register(api: TestClient, receipt: str) -> Response:
    return api.post(
        "/api/v1/auth/web/registration",
        json={"challenge_id": receipt, "device_name": "Painel de teste"},
    )


def web_login(api: TestClient, receipt: str) -> Response:
    return api.post(
        "/api/v1/auth/web/login",
        json={"challenge_id": receipt, "device_name": "Painel de teste"},
    )


def csrf_headers(api: TestClient) -> dict[str, str]:
    token = api.cookies.get(CSRF_COOKIE_NAME)
    assert token is not None
    return {"X-CSRF-Token": token}


def test_web_registration_sets_http_only_cookies_and_access_works(
    api: TestClient,
    sms_sender: RecordingSmsSender,
    db_session: Session,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")

    response = web_register(api, receipt)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["csrf_token"]
    assert body["user"]["status"] == "active"
    assert "refresh_token" not in body

    set_cookie = response.headers.get("set-cookie", "")
    assert REFRESH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth/web" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert CSRF_COOKIE_NAME in set_cookie
    assert api.cookies.get(REFRESH_COOKIE_NAME) is not None
    assert api.cookies.get(CSRF_COOKIE_NAME) == body["csrf_token"]

    me = api.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]

    assert db_session.scalar(
        select(SecurityEvent).where(SecurityEvent.event_type == "auth.registration_completed")
    )


def test_web_refresh_requires_csrf_and_rotates_cookies(
    api: TestClient,
    sms_sender: RecordingSmsSender,
    db_session: Session,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    registered = web_register(api, receipt)
    assert registered.status_code == 201
    original_csrf = registered.json()["csrf_token"]

    missing = api.post("/api/v1/auth/web/refresh")
    assert missing.status_code == 403
    assert missing.json() == {"detail": {"code": "csrf_failed"}}

    wrong = api.post(
        "/api/v1/auth/web/refresh",
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert wrong.status_code == 403
    assert wrong.json() == {"detail": {"code": "csrf_failed"}}

    refreshed = api.post(
        "/api/v1/auth/web/refresh",
        headers={"X-CSRF-Token": original_csrf},
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["access_token"] != registered.json()["access_token"]
    assert body["csrf_token"] != original_csrf
    assert api.cookies.get(CSRF_COOKIE_NAME) == body["csrf_token"]

    events = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert AUTH_REFRESH_ROTATED in events


def test_web_logout_revokes_session_and_clears_cookies(
    api: TestClient,
    sms_sender: RecordingSmsSender,
    db_session: Session,
) -> None:
    receipt = receipt_for(api, sms_sender, PHONE, "registration")
    registered = web_register(api, receipt)
    assert registered.status_code == 201
    csrf = registered.json()["csrf_token"]
    old_refresh = api.cookies.get(REFRESH_COOKIE_NAME)
    assert old_refresh is not None

    logout = api.post(
        "/api/v1/auth/web/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert logout.status_code == 204
    assert api.cookies.get(REFRESH_COOKIE_NAME) is None
    assert api.cookies.get(CSRF_COOKIE_NAME) is None
    assert AUTH_LOGOUT in set(db_session.scalars(select(SecurityEvent.event_type)))

    replay = api.post(
        "/api/v1/auth/web/refresh",
        headers={
            "Cookie": (f"{REFRESH_COOKIE_NAME}={old_refresh}; {CSRF_COOKIE_NAME}={csrf}"),
            "X-CSRF-Token": csrf,
        },
    )
    assert replay.status_code == 401
    assert replay.json() == {"detail": {"code": "invalid_refresh_token"}}


def test_web_login_existing_account_and_unknown_account(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    registration_receipt = receipt_for(api, sms_sender, PHONE, "registration")
    assert web_register(api, registration_receipt).status_code == 201
    csrf = api.cookies.get(CSRF_COOKIE_NAME)
    assert csrf is not None
    assert api.post("/api/v1/auth/web/logout", headers={"X-CSRF-Token": csrf}).status_code == 204

    login_receipt = receipt_for(api, sms_sender, PHONE, "login")
    logged_in = web_login(api, login_receipt)
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["user"]["status"] == "active"

    unknown_receipt = receipt_for(api, sms_sender, "+5511911112222", "login")
    unknown = web_login(api, unknown_receipt)
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": {"code": "account_not_found"}}


def test_web_registration_rejects_duplicate_phone(
    api: TestClient,
    sms_sender: RecordingSmsSender,
) -> None:
    first = receipt_for(api, sms_sender, PHONE, "registration")
    assert web_register(api, first).status_code == 201

    second = receipt_for(api, sms_sender, PHONE, "registration")
    duplicate = web_register(api, second)

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "phone_already_registered"}}
