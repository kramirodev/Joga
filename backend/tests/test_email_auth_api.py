"""Fluxos HTTP da credencial de e-mail e senha (ADR 0050)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.email.deliveries import EmailDeliveryService
from app.modules.email.models import EmailDelivery, UserEmail
from app.modules.email.sender import FakeSender
from app.modules.identity.clock import utcnow
from app.modules.identity.events import EMAIL_BUDGET_EXHAUSTED, EMAIL_BUDGET_WARNING
from app.modules.identity.models import PhoneChallenge, SecurityEvent, User, UserPassword
from scripts.deliver_emails import run_once_with_sender
from tests.email_helpers import (
    IDENTITY_SECRET,
    PASSWORD,
    active_sessions,
    bearer,
    code_for,
    deliver,
    email_settings,
    login_flow,
    post_code,
    post_verify,
    register_flow,
    seed_session,
    seed_user_with_email,
)
from tests.webauthn_authenticator import SoftAuthenticator


def _set_settings(api: TestClient, **overrides: object) -> None:
    api.app.dependency_overrides[get_settings] = lambda: email_settings(**overrides)


def test_registration_sets_password_and_login_works(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "senha@example.com")
    user_id = uuid.UUID(registered["user"]["id"])

    stored = db_session.get(UserPassword, user_id)
    assert stored is not None
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash

    logged = login_flow(email_api, "senha@example.com")
    assert logged["access_token"]


def test_weak_password_does_not_consume_registration_code(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    issued, code = code_for(email_api, db_session, sender, "fraca@example.com", "registration")
    verified = post_verify(email_api, issued["challenge_id"], code)
    weak = email_api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "fraca@example.com",
            "password": "curta",
        },
    )
    assert weak.status_code == 400
    assert weak.json() == {"detail": {"code": "weak_password"}}

    challenge = db_session.get(PhoneChallenge, uuid.UUID(verified.json()["challenge_id"]))
    assert challenge is not None and challenge.receipt_used_at is None

    strong = email_api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "fraca@example.com",
            "password": PASSWORD,
        },
    )
    assert strong.status_code == 201, strong.text


def test_code_login_is_not_part_of_contract(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    invalid_purpose = post_code(email_api, "jogador@example.com", "login")
    assert invalid_purpose.status_code == 422

    issued, code = code_for(email_api, db_session, sender, "codigo@example.com", "registration")
    verified = post_verify(email_api, issued["challenge_id"], code)
    old_login = email_api.post(
        "/api/v1/auth/email/login",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "codigo@example.com",
        },
    )
    assert old_login.status_code == 422


def test_registration_duplicate_with_uppercase_variation_is_rejected(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    register_flow(email_api, db_session, sender, "duplicado@example.com")
    assert db_session.scalar(select(func.count()).select_from(UserEmail)) == 1

    issued, code = code_for(
        email_api, db_session, sender, " DUPLICADO@Example.com ", "registration"
    )
    verified = post_verify(email_api, issued["challenge_id"], code)
    duplicate = email_api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": " DUPLICADO@Example.com ",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "email_already_registered"}}
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_wrong_expired_and_replayed_codes_are_rejected(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    issued, code = code_for(email_api, db_session, sender, "jogador@example.com", "registration")

    wrong = post_verify(email_api, issued["challenge_id"], "000000")
    assert wrong.status_code == 400
    assert wrong.json() == {"detail": {"code": "invalid_code_or_challenge"}}

    verified = post_verify(email_api, issued["challenge_id"], code)
    assert verified.status_code == 200
    replay = post_verify(email_api, issued["challenge_id"], code)
    assert replay.status_code == 400

    second, second_code = code_for(
        email_api, db_session, sender, "outro@example.com", "registration"
    )
    challenge = db_session.get(PhoneChallenge, uuid.UUID(second["challenge_id"]))
    assert challenge is not None
    challenge.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()
    expired = post_verify(email_api, second["challenge_id"], second_code)
    assert expired.status_code == 400


def test_attempt_limit_locks_challenge(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    issued, code = code_for(email_api, db_session, sender, "tentativas@example.com", "registration")
    for _ in range(5):
        assert post_verify(email_api, issued["challenge_id"], "000000").status_code == 400
    assert post_verify(email_api, issued["challenge_id"], code).status_code == 400


def test_resend_cooldown_returns_retry_after(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(email_api, email_resend_cooldown_seconds=60)
    assert post_code(email_api, "cooldown@example.com").status_code == 202
    blocked = post_code(email_api, "cooldown@example.com")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.json() == {"detail": {"code": "rate_limited"}}


def test_hourly_limit_per_address(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(
        email_api,
        email_max_per_address_per_hour=2,
        email_max_per_ip_per_hour=20,
    )
    assert post_code(email_api, "limite@example.com").status_code == 202
    assert post_code(email_api, "limite@example.com").status_code == 202
    assert post_code(email_api, "limite@example.com").status_code == 429


def test_hourly_limit_per_ip(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(
        email_api,
        email_max_per_address_per_hour=20,
        email_max_per_ip_per_hour=1,
    )
    assert post_code(email_api, "ip1@example.com").status_code == 202
    assert post_code(email_api, "ip2@example.com").status_code == 429


def test_password_reset_code_response_is_generic_for_existing_and_unknown(
    email_api: TestClient,
    db_session: Session,
) -> None:
    seed_user_with_email(db_session, "existe@example.com")
    db_session.commit()

    existing = post_code(email_api, "existe@example.com", "password_reset")
    unknown = post_code(email_api, "nao-existe@example.com", "password_reset")

    assert existing.status_code == unknown.status_code == 202
    assert existing.json().keys() == unknown.json().keys()
    assert existing.json()["resend_after_seconds"] == unknown.json()["resend_after_seconds"]
    assert "existe@example.com" not in existing.text
    assert "nao-existe@example.com" not in unknown.text


def test_login_is_generic_for_wrong_password_unknown_and_suspended(
    email_api: TestClient,
    db_session: Session,
) -> None:
    seed_user_with_email(db_session, "ativo@example.com", password=PASSWORD)
    seed_user_with_email(db_session, "suspenso@example.com", status="suspended", password=PASSWORD)
    seed_user_with_email(db_session, "semverificado@example.com", verified=False, password=PASSWORD)
    db_session.commit()

    cases = [
        ("ativo@example.com", "senha-errada"),
        ("nao-existe@example.com", PASSWORD),
        ("suspenso@example.com", PASSWORD),
        ("semverificado@example.com", PASSWORD),
    ]
    bodies = []
    for email, password in cases:
        response = email_api.post(
            "/api/v1/auth/email/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 401
        bodies.append(response.json())
    assert bodies.count({"detail": {"code": "invalid_credentials"}}) == len(cases)

    ok = login_flow(email_api, "ativo@example.com", password=PASSWORD)
    assert ok["access_token"]


def test_login_rate_limit_per_email(
    email_api: TestClient,
    db_session: Session,
) -> None:
    seed_user_with_email(db_session, "limite-login@example.com", password=PASSWORD)
    db_session.commit()
    _set_settings(
        email_api,
        email_login_max_per_email=2,
        email_login_max_per_ip=100,
    )

    for _ in range(2):
        assert (
            email_api.post(
                "/api/v1/auth/email/login",
                json={"email": "limite-login@example.com", "password": "errada"},
            ).status_code
            == 401
        )
    blocked = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "limite-login@example.com", "password": PASSWORD},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": {"code": "rate_limited"}}
    assert blocked.headers["Retry-After"]


def test_login_rate_limit_per_ip(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(
        email_api,
        email_login_max_per_email=100,
        email_login_max_per_ip=2,
    )
    for email in ("um@example.com", "dois@example.com"):
        assert (
            email_api.post(
                "/api/v1/auth/email/login",
                json={"email": email, "password": "errada"},
            ).status_code
            == 401
        )
    blocked = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "tres@example.com", "password": "errada"},
    )
    assert blocked.status_code == 429


def test_password_reset_revokes_all_sessions_and_changes_password(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "reset@example.com")
    user_id = uuid.UUID(registered["user"]["id"])
    assert active_sessions(db_session, user_id)

    issued, code = code_for(email_api, db_session, sender, "reset@example.com", "password_reset")
    verified = post_verify(email_api, issued["challenge_id"], code)
    new_password = "NovaSenhaBeta456"
    reset = email_api.post(
        "/api/v1/auth/email/password/reset",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "reset@example.com",
            "new_password": new_password,
        },
    )
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"status": "ok"}
    assert active_sessions(db_session, user_id) == []

    old = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "reset@example.com", "password": PASSWORD},
    )
    assert old.status_code == 401
    login_flow(email_api, "reset@example.com", password=new_password)

    replay = email_api.post(
        "/api/v1/auth/email/password/reset",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "reset@example.com",
            "new_password": "OutraSenhaBeta789",
        },
    )
    assert replay.status_code == 400
    assert replay.json() == {"detail": {"code": "invalid_password_reset"}}

    notice = db_session.scalar(
        select(EmailDelivery).where(EmailDelivery.kind == "password_changed")
    )
    assert notice is not None
    deliver(db_session, sender)
    assert sender.last_message() is not None
    assert sender.last_message().kind == "password_changed"


def test_password_reset_expired_code_is_rejected(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    register_flow(email_api, db_session, sender, "expira-reset@example.com")
    issued, code = code_for(
        email_api, db_session, sender, "expira-reset@example.com", "password_reset"
    )
    verified = post_verify(email_api, issued["challenge_id"], code)
    challenge = db_session.get(PhoneChallenge, uuid.UUID(verified.json()["challenge_id"]))
    assert challenge is not None
    challenge.consumed_at = utcnow() - timedelta(seconds=1_200)
    challenge.expires_at = utcnow() - timedelta(seconds=1_200)
    db_session.commit()

    response = email_api.post(
        "/api/v1/auth/email/password/reset",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "expira-reset@example.com",
            "new_password": "NovaSenhaBeta456",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_password_reset"}}


def test_password_reset_unknown_email_is_generic(
    email_api: TestClient,
    db_session: Session,
) -> None:
    issued = post_code(email_api, "nao-cadastrado@example.com", "password_reset")
    assert issued.status_code == 202
    verified = post_verify(email_api, issued.json()["challenge_id"], "123456")
    assert verified.status_code == 200

    response = email_api.post(
        "/api/v1/auth/email/password/reset",
        json={
            "challenge_id": issued.json()["challenge_id"],
            "email": "nao-cadastrado@example.com",
            "new_password": "NovaSenhaBeta456",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_password_reset"}}
    assert db_session.scalar(select(func.count()).select_from(User)) == 0


def test_password_change_keeps_current_session_and_revokes_others(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "troca-senha@example.com")
    token = str(registered["access_token"])
    user_id = uuid.UUID(registered["user"]["id"])
    _, extra_session = seed_session(db_session, user_id)
    db_session.commit()

    wrong = email_api.post(
        "/api/v1/me/password",
        json={"current_password": "errada", "new_password": "NovaSenhaBeta456"},
        headers=bearer(token),
    )
    assert wrong.status_code == 401
    assert wrong.json() == {"detail": {"code": "invalid_credentials"}}

    weak = email_api.post(
        "/api/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "curta"},
        headers=bearer(token),
    )
    assert weak.status_code == 400
    assert weak.json() == {"detail": {"code": "weak_password"}}

    changed = email_api.post(
        "/api/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "NovaSenhaBeta456"},
        headers=bearer(token),
    )
    assert changed.status_code == 204

    active_ids = {row.id for row in active_sessions(db_session, user_id)}
    assert extra_session not in active_ids
    assert email_api.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200

    old = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "troca-senha@example.com", "password": PASSWORD},
    )
    assert old.status_code == 401
    login_flow(email_api, "troca-senha@example.com", password="NovaSenhaBeta456")

    notice = db_session.scalar(
        select(EmailDelivery).where(EmailDelivery.kind == "password_changed")
    )
    assert notice is not None
    deliver(db_session, sender)
    assert sender.last_message() is not None
    assert sender.last_message().kind == "password_changed"


def test_email_change_requires_new_address_and_revokes_other_sessions(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "antigo@example.com")
    token = str(registered["access_token"])
    user_id = uuid.UUID(registered["user"]["id"])
    extra_token, extra_session_id = seed_session(db_session, user_id)
    assert extra_token
    db_session.commit()

    requested = email_api.post(
        "/api/v1/me/account/email/challenges",
        json={"new_email": "novo@example.com"},
        headers=bearer(token),
    )
    assert requested.status_code == 202, requested.text
    deliver(db_session, sender)
    message = sender.last_message()
    assert message is not None and message.code is not None
    assert message.to == "novo@example.com"

    changed = email_api.patch(
        "/api/v1/me/account/email",
        json={
            "new_email": "novo@example.com",
            "challenge_id": requested.json()["challenge_id"],
            "code": message.code,
        },
        headers=bearer(token),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["email"] == "novo@example.com"

    old = db_session.scalar(
        select(UserEmail).where(UserEmail.email_normalized == "antigo@example.com")
    )
    new = db_session.scalar(
        select(UserEmail).where(UserEmail.email_normalized == "novo@example.com")
    )
    assert old is not None and old.released_at is not None
    assert new is not None and new.verified_at is not None and new.is_primary

    active_ids = {row.id for row in active_sessions(db_session, user_id)}
    assert extra_session_id not in active_ids
    assert email_api.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200

    notice = db_session.scalar(
        select(EmailDelivery).where(EmailDelivery.kind == "email_change_notice")
    )
    assert notice is not None
    deliver(db_session, sender)
    assert sender.last_message() is not None
    assert sender.last_message().to == "antigo@example.com"
    assert sender.last_message().code is None

    old_login = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "antigo@example.com", "password": PASSWORD},
    )
    assert old_login.status_code == 401
    login_flow(email_api, "novo@example.com", password=PASSWORD)

    cooldown = email_api.post(
        "/api/v1/me/account/email/challenges",
        json={"new_email": "outro@example.com"},
        headers=bearer(token),
    )
    assert cooldown.status_code == 429
    assert cooldown.json() == {"detail": {"code": "email_change_cooldown"}}


def test_user_a_cannot_confirm_email_change_of_user_b(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    account_a = register_flow(email_api, db_session, sender, "a@example.com")
    account_b = register_flow(email_api, db_session, sender, "b@example.com")
    token_a = str(account_a["access_token"])
    token_b = str(account_b["access_token"])

    requested = email_api.post(
        "/api/v1/me/account/email/challenges",
        json={"new_email": "b-novo@example.com"},
        headers=bearer(token_b),
    )
    assert requested.status_code == 202
    deliver(db_session, sender)
    message = sender.last_message()
    assert message is not None and message.code is not None

    forged = email_api.patch(
        "/api/v1/me/account/email",
        json={
            "new_email": "b-novo@example.com",
            "challenge_id": requested.json()["challenge_id"],
            "code": message.code,
        },
        headers=bearer(token_a),
    )
    assert forged.status_code == 400
    credential_b = db_session.scalar(
        select(UserEmail).where(UserEmail.email_normalized == "b@example.com")
    )
    assert credential_b is not None and credential_b.released_at is None


def test_payer_email_put_does_not_change_login_credential(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "credencial@example.com")
    token = str(registered["access_token"])
    user_id = uuid.UUID(registered["user"]["id"])

    payer = email_api.put(
        "/api/v1/me/email",
        json={"email": "pagador@example.com"},
        headers=bearer(token),
    )
    assert payer.status_code == 200, payer.text
    assert payer.json() == {"email": "pagador@example.com"}

    user = db_session.get(User, user_id)
    assert user is not None and user.email == "pagador@example.com"

    listing = email_api.get("/api/v1/auth/emails", headers=bearer(token))
    assert listing.status_code == 200
    assert [item["email"] for item in listing.json()["emails"]] == ["credencial@example.com"]

    login_flow(email_api, "credencial@example.com")
    payer_login = email_api.post(
        "/api/v1/auth/email/login",
        json={"email": "pagador@example.com", "password": PASSWORD},
    )
    assert payer_login.status_code == 401
    assert payer_login.json() == {"detail": {"code": "invalid_credentials"}}


def test_disposable_domain_is_blocked(email_api: TestClient) -> None:
    blocked = post_code(email_api, "jogador@mailinator.com")
    assert blocked.status_code == 400
    assert blocked.json() == {"detail": {"code": "email_domain_not_allowed"}}


def test_signup_closed_blocks_registration_not_password_reset(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(email_api, signup_mode="closed")
    assert post_code(email_api, "novo@example.com", "registration").status_code == 403
    assert post_code(email_api, "existente@example.com", "password_reset").status_code == 202

    register = email_api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": str(uuid.uuid4()),
            "email": "novo@example.com",
            "password": PASSWORD,
        },
    )
    assert register.status_code == 403
    assert register.json() == {"detail": {"code": "signup_closed"}}


def test_budget_exhaustion_keeps_public_response_generic(
    email_api: TestClient,
    db_session: Session,
) -> None:
    _set_settings(email_api, email_daily_budget=1)
    EmailDeliveryService(
        db_session,
        provider="fake",
        daily_budget=1,
        secret=IDENTITY_SECRET,
    ).enqueue(
        "welcome",
        to="anterior@example.com",
        user_id=None,
        reference="previous",
        now=utcnow(),
    )
    db_session.commit()

    response = post_code(email_api, "novo@example.com")
    assert response.status_code == 202
    assert db_session.scalar(select(func.count()).select_from(EmailDelivery)) == 1
    event_types = set(db_session.scalars(select(SecurityEvent.event_type)))
    assert EMAIL_BUDGET_WARNING in event_types
    assert EMAIL_BUDGET_EXHAUSTED in event_types


def test_email_routes_disabled_by_flag(email_api: TestClient) -> None:
    _set_settings(
        email_api,
        auth_email_enabled=False,
        auth_phone_enabled=True,
        allow_phone_registration=True,
        email_provider="none",
    )
    response = post_code(email_api, "jogador@example.com")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "email_auth_disabled"}}


def test_phone_routes_disabled_by_flag(email_api: TestClient, db_session: Session) -> None:
    response = email_api.post(
        "/api/v1/auth/phone/challenges",
        json={"phone": "+5511987654321", "purpose": "login"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "phone_auth_disabled"}}


def test_email_account_can_register_passkey_without_password(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(email_api, db_session, sender, "passkey-login@example.com")
    token = str(registered["access_token"])
    user_id = uuid.UUID(registered["user"]["id"])
    settings = email_settings()
    auth = SoftAuthenticator(
        rp_id=settings.webauthn_rp_id,
        origin=settings.webauthn_origin_android,
        user_handle=user_id.bytes,
    )

    options = email_api.post(
        "/api/v1/auth/passkeys/registration/options",
        headers=bearer(token),
    )
    assert options.status_code == 200, options.text
    credential = auth.registration_credential(options.json()["public_key"]["challenge"])
    registered_key = email_api.post(
        "/api/v1/auth/passkeys/registration/verify",
        headers=bearer(token),
        json={
            "challenge_id": options.json()["challenge_id"],
            "credential": credential,
            "name": "Celular sem senha",
        },
    )
    assert registered_key.status_code == 201, registered_key.text

    auth_options = email_api.post(
        "/api/v1/auth/passkeys/authentication/options",
        json={"email": "passkey-login@example.com"},
    )
    assert auth_options.status_code == 200, auth_options.text
    assertion = auth.authentication_credential(auth_options.json()["public_key"]["challenge"])
    logged = email_api.post(
        "/api/v1/auth/passkeys/authentication/verify",
        json={
            "challenge_id": auth_options.json()["challenge_id"],
            "credential": assertion,
            "email": "passkey-login@example.com",
        },
    )
    assert logged.status_code == 200, logged.text
    assert logged.json()["access_token"]


def test_new_device_login_queues_security_alert(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    register_flow(email_api, db_session, sender, "dispositivo@example.com")
    login_flow(email_api, "dispositivo@example.com", device_name="Moto G")
    alerts = list(
        db_session.scalars(select(EmailDelivery).where(EmailDelivery.kind == "security_alert"))
    )
    assert len(alerts) == 1

    login_flow(email_api, "dispositivo@example.com", device_name="Moto G")
    alerts = list(
        db_session.scalars(select(EmailDelivery).where(EmailDelivery.kind == "security_alert"))
    )
    assert len(alerts) == 1


def test_list_credentials_only_returns_own_account(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    account_a = register_flow(email_api, db_session, sender, "lista-a@example.com")
    register_flow(email_api, db_session, sender, "lista-b@example.com")

    listing = email_api.get(
        "/api/v1/auth/emails",
        headers=bearer(str(account_a["access_token"])),
    )
    assert listing.status_code == 200
    emails = listing.json()["emails"]
    assert [item["email"] for item in emails] == ["lista-a@example.com"]
    assert set(emails[0]) == {"email", "is_primary", "verified_at", "created_at"}
    assert "email_hash" not in emails[0]
    assert "hard_bounce_count" not in emails[0]
    assert "undeliverable_at" not in emails[0]
    assert "password_hash" not in emails[0]
    assert "password_changed_at" not in emails[0]


def test_email_login_works_on_web_session(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    register_flow(email_api, db_session, sender, "painel@example.com")
    logged = email_api.post(
        "/api/v1/auth/web/email/login",
        json={
            "email": "painel@example.com",
            "password": PASSWORD,
            "device_name": "Painel",
        },
    )
    assert logged.status_code == 200, logged.text
    assert "joga_web_refresh" in logged.cookies
    assert logged.json()["access_token"]


def test_web_email_registration_sets_password(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    issued, code = code_for(
        email_api, db_session, sender, "painel-novo@example.com", "registration"
    )
    verified = post_verify(email_api, issued["challenge_id"], code)
    registered = email_api.post(
        "/api/v1/auth/web/email/registration",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": "painel-novo@example.com",
            "password": PASSWORD,
            "device_name": "Painel",
        },
    )
    assert registered.status_code == 201, registered.text
    assert "joga_web_refresh" in registered.cookies
    login_flow(email_api, "painel-novo@example.com")


def test_code_request_is_queued_and_delivered_by_scheduled_drain(
    email_api: TestClient,
    db_session: Session,
) -> None:
    response = post_code(email_api, "agendado@example.com")
    assert response.status_code == 202

    delivery = db_session.scalar(select(EmailDelivery).where(EmailDelivery.status == "queued"))
    assert delivery is not None

    sender = FakeSender()
    report = run_once_with_sender(
        db_session,
        sender,
        max_attempts=5,
        bounce_threshold=3,
    )
    assert report.sent == 1
    assert sender.last_message() is not None
    assert sender.last_message().code is not None

    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None and delivery.status == "sent"
