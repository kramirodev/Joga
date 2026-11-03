"""Registro de eventos de segurança sem PII em claro."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.identity.models import SecurityEvent

OTP_CHALLENGE_REQUESTED = "otp.challenge_requested"
OTP_CHALLENGE_VERIFIED = "otp.challenge_verified"
OTP_VERIFICATION_FAILED = "otp.verification_failed"
OTP_RATE_LIMITED = "otp.rate_limited"
AUTH_REGISTRATION_COMPLETED = "auth.registration_completed"
AUTH_LOGIN_COMPLETED = "auth.login_completed"
AUTH_REFRESH_ROTATED = "auth.refresh_rotated"
AUTH_REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
AUTH_LOGOUT = "auth.logout"
AUTH_LOGOUT_ALL = "auth.logout_all"
AUTH_PHONE_CHANGE_REQUESTED = "auth.phone_change_requested"
AUTH_PHONE_CHANGE_COMPLETED = "auth.phone_change_completed"
AUTH_PHONE_CHANGE_FAILED = "auth.phone_change_failed"
PASSKEY_REGISTRATION_STARTED = "passkey.registration_started"
PASSKEY_REGISTERED = "passkey.registered"
PASSKEY_AUTHENTICATION_STARTED = "passkey.authentication_started"
PASSKEY_AUTHENTICATED = "passkey.authenticated"
PASSKEY_REVOKED = "passkey.revoked"
PASSKEY_FAILED = "passkey.failed"
PASSKEY_RATE_LIMITED = "passkey.rate_limited"
AUTH_DEVICE_REVOKED = "auth.device_revoked"


def record_security_event(
    session: Session,
    event_type: str,
    *,
    user_id: uuid.UUID | None = None,
    ip_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adiciona o evento à transação atual; o chamador decide quando commitar.

    `details` nunca deve conter telefone, OTP, token ou IP em claro.
    """
    session.add(
        SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            ip_hash=ip_hash,
            details=details,
        )
    )
