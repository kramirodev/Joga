"""Testes dos endpoints de passkeys (SQLite em memória)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import (
    get_challenge_service,
    get_session,
    get_sms_sender,
)
from app.core.config import DEFAULT_PHONE_HASH_SECRET, DEFAULT_TOKEN_HASH_SECRET, Settings
from app.modules.identity.models import PasskeyChallenge, User, UserPhone
from app.modules.identity.otp import OtpPolicy, PhoneChallengeService
from app.modules.identity.phone import hash_phone
from app.modules.identity.sessions import SessionService
from app.modules.identity.sms import RecordingSmsSender
from tests.webauthn_authenticator import SoftAuthenticator

RP_ID = "joga-passkeys.vercel.app"
PHONE_A = "+5511987654321"
PHONE_B = "+5511911112222"
BASE_TIME = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


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


def make_user_with_tokens(session: Session) -> tuple[User, dict[str, str]]:
    user = User(status="active")
    session.add(user)
    session.flush()
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id)
    session.commit()
    return user, {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
    }


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def registration_options(api: TestClient, access_token: str) -> Response:
    return api.post(
        "/api/v1/auth/passkeys/registration/options",
        headers=bearer(access_token),
    )


def register_passkey(
    api: TestClient,
    access_token: str,
    authenticator: SoftAuthenticator,
) -> Response:
    options = registration_options(api, access_token)
    assert options.status_code == 200, options.text
    challenge = options.json()["public_key"]["challenge"]
    return api.post(
        "/api/v1/auth/passkeys/registration/verify",
        headers=bearer(access_token),
        json={
            "challenge_id": options.json()["challenge_id"],
            "credential": authenticator.registration_credential(challenge),
            "name": "Celular de teste",
        },
    )


def authentication_tokens(
    api: TestClient,
    authenticator: SoftAuthenticator,
) -> Response:
    options = api.post("/api/v1/auth/passkeys/authentication/options")
    assert options.status_code == 200, options.text
    challenge = options.json()["public_key"]["challenge"]
    return api.post(
        "/api/v1/auth/passkeys/authentication/verify",
        json={
            "challenge_id": options.json()["challenge_id"],
            "credential": authenticator.authentication_credential(challenge),
        },
    )


def test_passkey_registration_requires_authentication(api: TestClient) -> None:
    response = api.post("/api/v1/auth/passkeys/registration/options")

    assert response.status_code == 401


def test_register_and_login_with_passkey(
    api: TestClient,
    db_session: Session,
) -> None:
    user, tokens = make_user_with_tokens(db_session)
    settings = Settings(_env_file=None)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=settings.webauthn_origin_android,
        user_handle=user.id.bytes,
    )

    registered = register_passkey(api, tokens["access_token"], authenticator)

    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert body["name"] == "Celular de teste"
    assert body["credential_id"]

    listed = api.get("/api/v1/auth/passkeys", headers=bearer(tokens["access_token"]))
    assert listed.status_code == 200
    assert len(listed.json()["credentials"]) == 1

    authenticated = authentication_tokens(api, authenticator)

    assert authenticated.status_code == 200, authenticated.text
    login_tokens = authenticated.json()
    me = api.get(
        "/api/v1/auth/me",
        headers=bearer(login_tokens["access_token"]),
    )
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


def test_registration_rejects_invalid_assertion(
    api: TestClient,
    db_session: Session,
) -> None:
    user, tokens = make_user_with_tokens(db_session)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin="https://evil.example",
        user_handle=user.id.bytes,
    )

    response = register_passkey(api, tokens["access_token"], authenticator)

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_passkey"}}
    listed = api.get("/api/v1/auth/passkeys", headers=bearer(tokens["access_token"]))
    assert listed.json()["credentials"] == []


def test_revoked_credential_cannot_login(
    api: TestClient,
    db_session: Session,
) -> None:
    user, tokens = make_user_with_tokens(db_session)
    settings = Settings(_env_file=None)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=settings.webauthn_origin_android,
        user_handle=user.id.bytes,
    )
    registered = register_passkey(api, tokens["access_token"], authenticator)
    credential_id = registered.json()["credential_id"]

    revoked = api.delete(
        f"/api/v1/auth/passkeys/{credential_id}",
        headers=bearer(tokens["access_token"]),
    )
    assert revoked.status_code == 204

    denied = authentication_tokens(api, authenticator)

    assert denied.status_code == 400
    assert denied.json() == {"detail": {"code": "invalid_passkey"}}


def test_other_user_cannot_revoke_credential(
    api: TestClient,
    db_session: Session,
) -> None:
    owner, owner_tokens = make_user_with_tokens(db_session)
    _, other_tokens = make_user_with_tokens(db_session)
    settings = Settings(_env_file=None)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=settings.webauthn_origin_android,
        user_handle=owner.id.bytes,
    )
    registered = register_passkey(api, owner_tokens["access_token"], authenticator)
    credential_id = registered.json()["credential_id"]

    response = api.delete(
        f"/api/v1/auth/passkeys/{credential_id}",
        headers=bearer(other_tokens["access_token"]),
    )

    assert response.status_code == 404
    listed = api.get("/api/v1/auth/passkeys", headers=bearer(owner_tokens["access_token"]))
    assert len(listed.json()["credentials"]) == 1


def test_passkey_options_are_persisted(
    api: TestClient,
    db_session: Session,
) -> None:
    _, tokens = make_user_with_tokens(db_session)

    response = registration_options(api, tokens["access_token"])

    assert response.status_code == 200
    challenge_id = response.json()["challenge_id"]
    row = db_session.get(PasskeyChallenge, UUID(challenge_id))
    assert row is not None
    assert row.purpose == "registration"
    assert row.consumed_at is None


def test_authentication_options_are_public_and_persisted(
    api: TestClient,
    db_session: Session,
) -> None:
    response = api.post("/api/v1/auth/passkeys/authentication/options")

    assert response.status_code == 200
    challenge_id = response.json()["challenge_id"]
    row = db_session.get(PasskeyChallenge, UUID(challenge_id))
    assert row is not None
    assert row.purpose == "authentication"
    assert row.user_id is None


def test_recovery_uses_passkey_and_new_phone(
    api: TestClient,
    db_session: Session,
    sms_sender: RecordingSmsSender,
) -> None:
    user = User(status="active")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserPhone(
            user_id=user.id,
            phone_hash=hash_phone(PHONE_A, DEFAULT_PHONE_HASH_SECRET),
            is_primary=True,
            verified_at=BASE_TIME,
        )
    )
    original = SessionService(
        db_session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id)
    db_session.commit()

    settings = Settings(_env_file=None)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=settings.webauthn_origin_android,
        user_handle=user.id.bytes,
    )
    registered = register_passkey(api, original.access_token, authenticator)
    assert registered.status_code == 201
    assert (
        api.post(
            "/api/v1/auth/logout",
            headers=bearer(original.access_token),
        ).status_code
        == 204
    )

    recovered = authentication_tokens(api, authenticator)
    assert recovered.status_code == 200, recovered.text
    recovered_access = recovered.json()["access_token"]

    requested = api.post(
        "/api/v1/auth/phone-change/challenges",
        headers=bearer(recovered_access),
        json={"new_phone": PHONE_B},
    )
    assert requested.status_code == 202, requested.text
    message = sms_sender.last_message()
    assert message is not None
    confirmed = api.post(
        "/api/v1/auth/phone-change",
        headers=bearer(recovered_access),
        json={
            "challenge_id": requested.json()["challenge_id"],
            "code": message.code,
        },
    )

    assert confirmed.status_code == 204
    old_phone = db_session.scalar(
        select(UserPhone).where(
            UserPhone.phone_hash == hash_phone(PHONE_A, DEFAULT_PHONE_HASH_SECRET)
        )
    )
    new_phone = db_session.scalar(
        select(UserPhone).where(
            UserPhone.phone_hash == hash_phone(PHONE_B, DEFAULT_PHONE_HASH_SECRET),
            UserPhone.released_at.is_(None),
        )
    )
    assert old_phone is not None and old_phone.released_at is not None
    assert new_phone is not None
    assert (
        api.get(
            "/api/v1/auth/me",
            headers=bearer(recovered_access),
        ).status_code
        == 401
    )
