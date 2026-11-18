"""Utilitários compartilhados dos testes de e-mail (sem rede)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.email.dispatcher import dispatch_email_deliveries
from app.modules.email.sender import FakeSender
from app.modules.identity.models import Session as SessionRecord
from app.modules.identity.models import User, UserPassword
from app.modules.identity.passwords import PasswordService
from app.modules.identity.sessions import SessionService

TOKEN_SECRET = "local-token-development-only-change-me"
IDENTITY_SECRET = "local-development-only-change-me"
PASSWORD = "SenhaSeguraBeta123"
BASE_TIME = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

_FAST_HASHER = PasswordHasher(memory_cost=1024, time_cost=1, parallelism=1)
_FAST_DUMMY = _FAST_HASHER.hash("dummy-password-not-used")


def fast_password_service() -> PasswordService:
    """Argon2id com custo reduzido apenas nos testes de API."""
    return PasswordService(_FAST_HASHER, dummy_hash=_FAST_DUMMY)


def email_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "local",
        "auth_email_enabled": True,
        "auth_phone_enabled": False,
        "allow_phone_registration": False,
        "allow_email_registration": True,
        "phone_required_for_booking": False,
        "signup_mode": "open",
        "email_provider": "fake",
        "email_from": "no-reply@joga.example",
        "email_from_name": "JOGA",
        "email_api_key": SecretStr("test-key"),
        "email_daily_budget": 250,
        "email_resend_cooldown_seconds": 0,
        "signup_max_per_ip_per_day": 50,
        "dev_fixed_otp": "123456",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def post_code(api: TestClient, email: str, purpose: str = "registration"):
    return api.post(
        "/api/v1/auth/email/code",
        json={"email": email, "purpose": purpose},
    )


def post_verify(api: TestClient, challenge_id: str, code: str):
    return api.post(
        "/api/v1/auth/email/verify",
        json={"challenge_id": challenge_id, "code": code},
    )


def deliver(session: Session, sender: FakeSender) -> None:
    dispatch_email_deliveries(session, sender, max_attempts=5, bounce_threshold=3)
    session.commit()


def code_for(api: TestClient, session: Session, sender: FakeSender, email: str, purpose: str):
    response = post_code(api, email, purpose)
    assert response.status_code == 202, response.text
    deliver(session, sender)
    message = sender.last_message()
    assert message is not None and message.code is not None
    return response.json(), message.code


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_user_with_email(
    session: Session,
    email: str,
    *,
    verified: bool = True,
    status: str = "active",
    password: str | None = PASSWORD,
) -> tuple[uuid.UUID, uuid.UUID]:
    from app.modules.email.models import UserEmail

    user = User(status=status)
    session.add(user)
    session.flush()
    credential = UserEmail(
        user_id=user.id,
        email_normalized=email,
        verified_at=BASE_TIME if verified else None,
        is_primary=True,
    )
    session.add(credential)
    if password is not None:
        session.add(
            UserPassword(
                user_id=user.id,
                password_hash=fast_password_service().hash(password),
                password_changed_at=BASE_TIME,
            )
        )
    session.flush()
    return user.id, credential.id


def seed_session(session: Session, user_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    tokens = SessionService(
        session,
        TOKEN_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id, now=BASE_TIME)
    session.flush()
    return tokens.access_token, tokens.session_id


def register_flow(
    api: TestClient,
    session: Session,
    sender: FakeSender,
    email: str,
    *,
    password: str = PASSWORD,
    display_name: str | None = "Jogador",
) -> dict[str, object]:
    issued, code = code_for(api, session, sender, email, "registration")
    verified = post_verify(api, issued["challenge_id"], code)
    assert verified.status_code == 200, verified.text
    registered = api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )
    assert registered.status_code == 201, registered.text
    return registered.json()


def login_flow(
    api: TestClient,
    email: str,
    *,
    password: str = PASSWORD,
    device_name: str | None = None,
) -> dict[str, object]:
    logged = api.post(
        "/api/v1/auth/email/login",
        json={
            "email": email,
            "password": password,
            "device_name": device_name,
        },
    )
    assert logged.status_code == 200, logged.text
    return logged.json()


def active_sessions(session: Session, user_id: uuid.UUID) -> list[SessionRecord]:
    from sqlalchemy import select

    return list(
        session.scalars(
            select(SessionRecord).where(
                SessionRecord.user_id == user_id,
                SessionRecord.revoked_at.is_(None),
            )
        )
    )
