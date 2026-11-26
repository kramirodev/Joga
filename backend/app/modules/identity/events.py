"""Registro de eventos de segurança sem PII em claro."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core import request_context
from app.modules.identity.models import SecurityEvent
from app.modules.observability.redaction import sanitize_details, sanitize_user_agent

OTP_CHALLENGE_REQUESTED = "otp.challenge_requested"
OTP_CHALLENGE_VERIFIED = "otp.challenge_verified"
OTP_VERIFICATION_FAILED = "otp.verification_failed"
OTP_RATE_LIMITED = "otp.rate_limited"
AUTH_REGISTRATION_COMPLETED = "auth.registration_completed"
AUTH_LOGIN_COMPLETED = "auth.login_completed"
AUTH_REFRESH_ROTATED = "auth.refresh_rotated"
AUTH_REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
AUTH_REFRESH_GRACE_USED = "auth.refresh_grace_used"
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

# Credencial de e-mail no beta (ADR 0050). Nenhum evento carrega endereço,
# código ou hash; apenas tipo, finalidade e motivo.
EMAIL_CHALLENGE_REQUESTED = "email.challenge_requested"
EMAIL_CHALLENGE_VERIFIED = "email.challenge_verified"
EMAIL_VERIFICATION_FAILED = "email.verification_failed"
EMAIL_RATE_LIMITED = "email.rate_limited"
EMAIL_REGISTRATION_COMPLETED = "auth.email_registration_completed"
EMAIL_LOGIN_COMPLETED = "auth.email_login_completed"
EMAIL_LOGIN_FAILED = "auth.email_login_failed"
EMAIL_PASSWORD_RESET_COMPLETED = "auth.email_password_reset_completed"
EMAIL_PASSWORD_RESET_FAILED = "auth.email_password_reset_failed"
EMAIL_PASSWORD_CHANGED = "auth.email_password_changed"
EMAIL_CHANGE_REQUESTED = "auth.email_change_requested"
EMAIL_CHANGE_COMPLETED = "auth.email_change_completed"
EMAIL_CHANGE_FAILED = "auth.email_change_failed"
EMAIL_SIGNUP_BLOCKED = "email.signup_blocked"
EMAIL_BUDGET_WARNING = "email.budget_warning"
EMAIL_BUDGET_EXHAUSTED = "email.budget_exhausted"
EMAIL_BOUNCE = "email.bounce"
EMAIL_DELIVERY_FAILED = "email.delivery_failed"

# Sinais gerados pelo middleware HTTP (ADR 0078).
HTTP_UNAUTHORIZED = "http.unauthorized"
HTTP_FORBIDDEN = "http.forbidden"
HTTP_RATE_LIMITED = "http.rate_limited"

_FAILURE_MARKERS = (
    "failed",
    "failure",
    "reuse",
    "rate_limited",
    "blocked",
    "revoked",
    "exhausted",
    "bounce",
)


def _infer_result(event_type: str) -> str:
    lowered = event_type.lower()
    return "failure" if any(marker in lowered for marker in _FAILURE_MARKERS) else "success"


def record_security_event(
    session: Session,
    event_type: str,
    *,
    user_id: uuid.UUID | None = None,
    ip_hash: str | None = None,
    ip: str | None = None,
    request_id: str | None = None,
    endpoint: str | None = None,
    user_agent: str | None = None,
    result: str | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityEvent:
    """Adiciona o evento à transação atual; o chamador decide quando commitar.

    ``details`` nunca deve conter telefone, OTP, token ou IP em claro. O IP
    completo é preenchido a partir do contexto da requisição (resolvido na
    borda) e só é exposto a admin de plataforma. A redação é aplicada mesmo que
    o chamador erre.
    """
    event = SecurityEvent(
        user_id=user_id if user_id is not None else request_context.current_user_id(),
        event_type=event_type,
        ip_hash=ip_hash if ip_hash is not None else request_context.current_ip_hash(),
        ip=ip if ip is not None else request_context.current_ip(),
        request_id=(request_id if request_id is not None else request_context.current_request_id()),
        endpoint=endpoint if endpoint is not None else request_context.current_endpoint(),
        user_agent=sanitize_user_agent(
            user_agent if user_agent is not None else request_context.current_user_agent()
        ),
        result=result if result is not None else _infer_result(event_type),
        details=sanitize_details(details),
    )
    session.add(event)
    return event
