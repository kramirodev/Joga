"""Endpoints da credencial de e-mail e senha (ADR 0050)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import (
    TokenResponse,
    UserSummary,
    get_current_session,
    get_device_service,
    get_session_service,
)
from app.api.v1.auth_guards import (
    require_email_auth_enabled,
    require_email_registration_allowed,
)
from app.core.config import Settings, get_settings
from app.core.text import OptionalDisplayName, OptionalFreeText
from app.infrastructure.database.dependency import get_session
from app.modules.email.addresses import InvalidEmail, hash_email, normalize_email
from app.modules.email.alerts import queue_security_alert
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.email.models import UserEmail
from app.modules.identity.clock import ensure_utc
from app.modules.identity.devices import DeviceService
from app.modules.identity.email_accounts import (
    DisposableEmailDomain,
    EmailAccountService,
    EmailAlreadyRegistered,
    EmailChangeCooldown,
    EmailUnchanged,
    InvalidCredentials,
    InvalidEmailReceipt,
    InvalidPasswordReset,
)
from app.modules.identity.email_challenges import EmailChallengeService
from app.modules.identity.events import (
    EMAIL_CHALLENGE_REQUESTED,
    EMAIL_CHALLENGE_VERIFIED,
    EMAIL_CHANGE_COMPLETED,
    EMAIL_CHANGE_FAILED,
    EMAIL_CHANGE_REQUESTED,
    EMAIL_LOGIN_COMPLETED,
    EMAIL_LOGIN_FAILED,
    EMAIL_PASSWORD_CHANGED,
    EMAIL_PASSWORD_RESET_COMPLETED,
    EMAIL_PASSWORD_RESET_FAILED,
    EMAIL_RATE_LIMITED,
    EMAIL_REGISTRATION_COMPLETED,
    EMAIL_SIGNUP_BLOCKED,
    EMAIL_VERIFICATION_FAILED,
    record_security_event,
)
from app.modules.identity.otp import (
    AttemptsExceeded,
    ChallengePurpose,
    ExpiredChallenge,
    HourlyLimitReached,
    InvalidChallenge,
    InvalidCode,
    IpLimitReached,
    OtpPolicy,
    ResendTooSoon,
)
from app.modules.identity.passwords import PasswordInput, PasswordPolicyError, PasswordService
from app.modules.identity.phone import hash_ip
from app.modules.identity.sessions import (
    AuthenticatedSession,
    IssuedTokens,
    SessionService,
)
from app.modules.ratelimit.service import RateLimitExceeded, enforce

router = APIRouter(
    tags=["email-auth"],
    dependencies=[Depends(require_email_auth_enabled)],
)

SIGNUP_SCOPE = "signup_email_ip"
LOGIN_WINDOW_SECONDS = 15 * 60
REQUEST_PURPOSES = {
    "registration": ChallengePurpose.email_verification,
    "password_reset": ChallengePurpose.password_reset,
}


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    purpose: Literal["registration", "password_reset"]


class EmailVerifyRequest(BaseModel):
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class EmailRegisterRequest(BaseModel):
    challenge_id: UUID
    email: str = Field(min_length=3, max_length=254)
    password: PasswordInput = Field(min_length=1, max_length=256)
    display_name: OptionalDisplayName = Field(default=None)
    device_name: OptionalFreeText = Field(default=None, max_length=80)
    platform: Literal["android", "ios", "web", "unknown"] = "unknown"


class EmailLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: PasswordInput = Field(min_length=1, max_length=256)
    device_name: OptionalFreeText = Field(default=None, max_length=80)
    platform: Literal["android", "ios", "web", "unknown"] = "unknown"


class EmailPasswordResetRequest(BaseModel):
    challenge_id: UUID
    email: str = Field(min_length=3, max_length=254)
    new_password: PasswordInput = Field(min_length=1, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: PasswordInput = Field(min_length=1, max_length=256)
    new_password: PasswordInput = Field(min_length=1, max_length=256)


class EmailChangeChallengeRequest(BaseModel):
    new_email: str = Field(min_length=3, max_length=254)


class EmailChangeRequest(BaseModel):
    new_email: str = Field(min_length=3, max_length=254)
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class EmailChallengeResponse(BaseModel):
    challenge_id: UUID
    expires_at: datetime
    resend_after_seconds: int


class EmailVerifyResponse(BaseModel):
    challenge_id: UUID
    purpose: ChallengePurpose
    verified_at: datetime
    receipt_expires_at: datetime


class EmailCredentialView(BaseModel):
    email: str
    is_primary: bool
    verified_at: datetime | None
    created_at: datetime


class EmailCredentialListResponse(BaseModel):
    emails: list[EmailCredentialView]


class PasswordResetResponse(BaseModel):
    status: str = "ok"


def _error(
    status_code: int,
    code: str,
    *,
    retry_after_seconds: int | None = None,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after_seconds)} if retry_after_seconds is not None else None
    return HTTPException(
        status_code=status_code,
        detail={"code": code},
        headers=headers,
    )


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ip_hash(request: Request, settings: Settings) -> str | None:
    ip = _request_ip(request)
    return hash_ip(ip, settings.phone_hash_secret.get_secret_value()) if ip else None


def get_password_service() -> PasswordService:
    return PasswordService()


def get_email_delivery_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailDeliveryService:
    return EmailDeliveryService(
        session,
        provider=settings.email_provider,
        daily_budget=settings.email_daily_budget,
        secret=settings.phone_hash_secret.get_secret_value(),
        max_attempts=settings.email_max_delivery_attempts,
        bounce_threshold=settings.email_bounce_threshold,
    )


def get_email_challenge_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
) -> EmailChallengeService:
    policy = OtpPolicy(
        ttl_seconds=settings.email_code_ttl_seconds,
        max_attempts=settings.otp_max_attempts,
        resend_cooldown_seconds=settings.email_resend_cooldown_seconds,
        max_per_hour=settings.email_max_per_address_per_hour,
        max_per_ip_per_hour=settings.email_max_per_ip_per_hour,
        receipt_ttl_seconds=settings.otp_receipt_ttl_seconds,
        fixed_code=settings.dev_fixed_otp,
    )
    return EmailChallengeService(
        session,
        deliveries,
        settings.phone_hash_secret.get_secret_value(),
        policy,
        disposable_domains=settings.email_disposable_domain_set,
    )


def get_email_account_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    challenges: Annotated[EmailChallengeService, Depends(get_email_challenge_service)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> EmailAccountService:
    return EmailAccountService(
        session,
        challenges,
        deliveries,
        passwords,
        settings.phone_hash_secret.get_secret_value(),
        receipt_ttl_seconds=settings.otp_receipt_ttl_seconds,
        change_cooldown_hours=settings.email_change_cooldown_hours,
    )


def _issue_session(
    sessions: SessionService,
    devices: DeviceService,
    user_id: UUID,
    *,
    device_name: str | None,
    platform: str,
) -> IssuedTokens:
    device_id = None
    if device_name:
        device_id = devices.register(user_id, device_name, platform).id
    return sessions.issue(user_id, device_id=device_id)


def _token_response(tokens: IssuedTokens, user: UserSummary) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
        user=user,
    )


def _credential_view(item: UserEmail) -> EmailCredentialView:
    return EmailCredentialView(
        email=item.email_normalized,
        is_primary=item.is_primary,
        verified_at=ensure_utc(item.verified_at) if item.verified_at else None,
        created_at=ensure_utc(item.created_at),
    )


def _record_rate_limited(
    session: Session,
    *,
    operation: str,
    reason: str,
    ip_hash: str | None,
    user_id: UUID | None = None,
) -> None:
    record_security_event(
        session,
        EMAIL_RATE_LIMITED,
        user_id=user_id,
        ip_hash=ip_hash,
        details={"operation": operation, "reason": reason},
    )


def _challenge_response(
    challenge_id: UUID,
    expires_at: datetime,
    resend_after_seconds: int,
) -> EmailChallengeResponse:
    return EmailChallengeResponse(
        challenge_id=challenge_id,
        expires_at=expires_at,
        resend_after_seconds=resend_after_seconds,
    )


def _failure_reason(error: Exception) -> str:
    if isinstance(error, ExpiredChallenge):
        return "expired"
    if isinstance(error, AttemptsExceeded):
        return "attempts"
    if isinstance(error, InvalidCode):
        return "code"
    return "invalid"


def enforce_login_limits(
    session: Session,
    settings: Settings,
    *,
    email: str,
    request_ip: str | None,
) -> tuple[str, str | None]:
    """Aplica 10/15 min por e-mail e 30/15 min por IP ao login por senha."""
    normalized = normalize_email(email)
    ip_hash = (
        hash_ip(request_ip, settings.phone_hash_secret.get_secret_value()) if request_ip else None
    )
    email_key = hash_email(normalized, settings.phone_hash_secret.get_secret_value())
    enforce(
        session,
        scope="email_login_address",
        key=email_key,
        limit=settings.email_login_max_per_email,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    enforce(
        session,
        scope="email_login_ip",
        key=ip_hash or "unknown",
        limit=settings.email_login_max_per_ip,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    return normalized, ip_hash


@router.post(
    "/auth/email/code",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EmailChallengeResponse,
)
def request_email_code(
    payload: EmailCodeRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    challenges: Annotated[EmailChallengeService, Depends(get_email_challenge_service)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
) -> EmailChallengeResponse:
    """Solicita código de verificação ou reset sem revelar existência de conta."""
    purpose = REQUEST_PURPOSES[payload.purpose]
    if purpose is ChallengePurpose.email_verification:
        if settings.signup_mode == "closed":
            raise _error(status.HTTP_403_FORBIDDEN, "signup_closed")
        if not settings.allow_email_registration:
            raise _error(status.HTTP_403_FORBIDDEN, "email_registration_disabled")

    ip_hash = _ip_hash(request, settings)
    try:
        if purpose is ChallengePurpose.password_reset:
            challenge_id, expires_at, resend_after = accounts.request_password_reset(
                payload.email,
                request_ip=_request_ip(request),
            )
        else:
            issued = challenges.request(
                payload.email,
                purpose,
                request_ip=_request_ip(request),
            )
            challenge_id = issued.challenge_id
            expires_at = issued.expires_at
            resend_after = issued.resend_after_seconds
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except DisposableEmailDomain:
        record_security_event(
            session,
            EMAIL_SIGNUP_BLOCKED,
            ip_hash=ip_hash,
            details={"reason": "disposable_domain", "purpose": payload.purpose},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "email_domain_not_allowed") from None
    except ResendTooSoon as error:
        _record_rate_limited(
            session,
            operation=payload.purpose,
            reason="resend",
            ip_hash=ip_hash,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None
    except (HourlyLimitReached, IpLimitReached):
        _record_rate_limited(
            session,
            operation=payload.purpose,
            reason="hourly",
            ip_hash=ip_hash,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None

    record_security_event(
        session,
        EMAIL_CHALLENGE_REQUESTED,
        ip_hash=ip_hash,
        details={"purpose": payload.purpose},
    )
    session.commit()
    return _challenge_response(challenge_id, expires_at, resend_after)


@router.post("/auth/email/verify", response_model=EmailVerifyResponse)
def verify_email_code(
    payload: EmailVerifyRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    challenges: Annotated[EmailChallengeService, Depends(get_email_challenge_service)],
) -> EmailVerifyResponse:
    """Valida o código e devolve o recibo curto; nunca devolve o e-mail."""
    ip_hash = _ip_hash(request, settings)
    try:
        verified = challenges.verify(payload.challenge_id, payload.code)
    except (InvalidChallenge, ExpiredChallenge, AttemptsExceeded, InvalidCode) as error:
        record_security_event(
            session,
            EMAIL_VERIFICATION_FAILED,
            ip_hash=ip_hash,
            details={"reason": _failure_reason(error)},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_code_or_challenge") from None

    record_security_event(
        session,
        EMAIL_CHALLENGE_VERIFIED,
        ip_hash=ip_hash,
        details={"purpose": verified.purpose.value},
    )
    session.commit()
    return EmailVerifyResponse(
        challenge_id=verified.challenge_id,
        purpose=verified.purpose,
        verified_at=verified.verified_at,
        receipt_expires_at=verified.receipt_expires_at,
    )


@router.post(
    "/auth/email/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    dependencies=[Depends(require_email_registration_allowed)],
)
def register_with_email(
    payload: EmailRegisterRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
) -> TokenResponse:
    """Cria conta com senha a partir de um recibo verificado."""
    ip_hash = _ip_hash(request, settings)
    try:
        enforce(
            session,
            scope=SIGNUP_SCOPE,
            key=ip_hash or "unknown",
            limit=settings.signup_max_per_ip_per_day,
            window_seconds=86_400,
        )
    except RateLimitExceeded as error:
        _record_rate_limited(
            session,
            operation="register",
            reason="ip_daily",
            ip_hash=ip_hash,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None

    try:
        account = accounts.register(
            payload.challenge_id,
            payload.email,
            payload.password,
            display_name=payload.display_name,
        )
    except PasswordPolicyError:
        raise _error(status.HTTP_400_BAD_REQUEST, "weak_password") from None
    except InvalidEmailReceipt:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_receipt") from None
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except EmailAlreadyRegistered:
        raise _error(status.HTTP_409_CONFLICT, "email_already_registered") from None
    except IntegrityError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "email_already_registered") from None

    tokens = _issue_session(
        sessions,
        devices,
        account.id,
        device_name=payload.device_name,
        platform=payload.platform,
    )
    try:
        welcome_email = normalize_email(payload.email)
    except InvalidEmail:  # pragma: no cover - validado no serviço
        welcome_email = payload.email
    try:
        deliveries.enqueue(
            "welcome",
            to=welcome_email,
            user_id=account.id,
            reference=str(account.id),
            context={"display_name": payload.display_name},
        )
    except EmailBudgetExhausted:
        pass
    record_security_event(session, EMAIL_REGISTRATION_COMPLETED, user_id=account.id)
    session.commit()
    return _token_response(
        tokens,
        UserSummary(id=account.id, status=account.status),
    )


@router.post("/auth/email/login", response_model=TokenResponse)
def login_with_email(
    payload: EmailLoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
) -> TokenResponse:
    """Autentica e-mail + senha com erro genérico e rate limit."""
    try:
        normalized, ip_hash = enforce_login_limits(
            session,
            settings,
            email=payload.email,
            request_ip=_request_ip(request),
        )
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except RateLimitExceeded as error:
        _record_rate_limited(
            session,
            operation="login",
            reason="rate_limit",
            ip_hash=_ip_hash(request, settings),
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None

    try:
        account = accounts.authenticate(normalized, payload.password)
    except InvalidCredentials:
        record_security_event(
            session,
            EMAIL_LOGIN_FAILED,
            ip_hash=ip_hash,
            details={"reason": "credentials"},
        )
        session.commit()
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_credentials") from None

    new_device = bool(payload.device_name) and not devices.has_named_device(
        account.id, payload.device_name or ""
    )
    tokens = _issue_session(
        sessions,
        devices,
        account.id,
        device_name=payload.device_name,
        platform=payload.platform,
    )
    if new_device:
        queue_security_alert(
            session,
            deliveries,
            user_id=account.id,
            reference=f"login:{uuid.uuid4()}",
            device_label=payload.device_name,
        )
    record_security_event(session, EMAIL_LOGIN_COMPLETED, user_id=account.id)
    session.commit()
    return _token_response(
        tokens,
        UserSummary(id=account.id, status=account.status),
    )


@router.post("/auth/email/password/reset", response_model=PasswordResetResponse)
def reset_email_password(
    payload: EmailPasswordResetRequest,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> PasswordResetResponse:
    """Consome o código de reset, troca a senha e revoga todas as sessões."""
    try:
        account = accounts.reset_password(
            payload.challenge_id,
            payload.email,
            payload.new_password,
        )
    except PasswordPolicyError:
        raise _error(status.HTTP_400_BAD_REQUEST, "weak_password") from None
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except (InvalidEmailReceipt, InvalidPasswordReset):
        record_security_event(
            session,
            EMAIL_PASSWORD_RESET_FAILED,
            details={"reason": "invalid"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_password_reset") from None

    sessions.revoke_all(account.id, reason="password_reset")
    record_security_event(
        session,
        EMAIL_PASSWORD_RESET_COMPLETED,
        user_id=account.id,
    )
    session.commit()
    return PasswordResetResponse()


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChangeRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """Troca a senha da sessão atual, mantendo-a e revogando as demais."""
    try:
        accounts.change_password(
            current.user_id,
            payload.current_password,
            payload.new_password,
        )
    except PasswordPolicyError:
        raise _error(status.HTTP_400_BAD_REQUEST, "weak_password") from None
    except InvalidCredentials:
        record_security_event(
            session,
            EMAIL_LOGIN_FAILED,
            user_id=current.user_id,
            details={"reason": "password_change"},
        )
        session.commit()
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_credentials") from None

    sessions.revoke_others(
        current.user_id,
        keep_session_id=current.session_id,
        reason="password_change",
    )
    record_security_event(session, EMAIL_PASSWORD_CHANGED, user_id=current.user_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/emails", response_model=EmailCredentialListResponse)
def list_my_emails(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
) -> EmailCredentialListResponse:
    """Lista apenas as credenciais da própria conta."""
    return EmailCredentialListResponse(
        emails=[_credential_view(item) for item in accounts.list_credentials(current.user_id)]
    )


@router.post(
    "/me/account/email/challenges",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EmailChallengeResponse,
)
def request_email_change(
    payload: EmailChangeChallengeRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
) -> EmailChallengeResponse:
    """Envia o código de troca ao endereço novo da conta autenticada."""
    ip_hash = _ip_hash(request, settings)
    try:
        challenge_id, expires_at, resend_after = accounts.request_change(
            current.user_id,
            payload.new_email,
            request_ip=_request_ip(request),
        )
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except DisposableEmailDomain:
        raise _error(status.HTTP_400_BAD_REQUEST, "email_domain_not_allowed") from None
    except EmailUnchanged:
        raise _error(status.HTTP_400_BAD_REQUEST, "email_unchanged") from None
    except EmailChangeCooldown as error:
        _record_rate_limited(
            session,
            operation="email_change",
            reason="cooldown",
            ip_hash=ip_hash,
            user_id=current.user_id,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "email_change_cooldown",
            retry_after_seconds=error.retry_after_seconds,
        ) from None
    except ResendTooSoon as error:
        _record_rate_limited(
            session,
            operation="email_change",
            reason="resend",
            ip_hash=ip_hash,
            user_id=current.user_id,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None
    except (HourlyLimitReached, IpLimitReached):
        _record_rate_limited(
            session,
            operation="email_change",
            reason="hourly",
            ip_hash=ip_hash,
            user_id=current.user_id,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None

    record_security_event(session, EMAIL_CHANGE_REQUESTED, user_id=current.user_id)
    session.commit()
    return _challenge_response(challenge_id, expires_at, resend_after)


@router.patch("/me/account/email", response_model=EmailCredentialView)
def change_my_email(
    payload: EmailChangeRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> EmailCredentialView:
    """Troca a credencial, avisa o endereço antigo e revoga outras sessões."""
    try:
        accounts.confirm_change(
            current.user_id,
            payload.new_email,
            payload.challenge_id,
            payload.code,
        )
    except (
        InvalidEmailReceipt,
        InvalidEmail,
        InvalidChallenge,
        ExpiredChallenge,
        AttemptsExceeded,
        InvalidCode,
    ):
        record_security_event(
            session,
            EMAIL_CHANGE_FAILED,
            user_id=current.user_id,
            details={"reason": "invalid"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email_change") from None
    except EmailAlreadyRegistered:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "email_already_registered") from None
    except EmailUnchanged:
        session.rollback()
        raise _error(status.HTTP_400_BAD_REQUEST, "email_unchanged") from None
    except EmailChangeCooldown as error:
        session.rollback()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "email_change_cooldown",
            retry_after_seconds=error.retry_after_seconds,
        ) from None

    sessions.revoke_others(current.user_id, keep_session_id=current.session_id)
    record_security_event(session, EMAIL_CHANGE_COMPLETED, user_id=current.user_id)
    session.commit()
    credential = accounts.primary_email(current.user_id)
    if credential is None:  # pragma: no cover - a troca acabou de criar a primária
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email_change") from None
    return _credential_view(credential)


__all__ = [
    "EmailChallengeResponse",
    "EmailCredentialView",
    "EmailLoginRequest",
    "EmailPasswordResetRequest",
    "EmailRegisterRequest",
    "enforce_login_limits",
    "get_email_account_service",
    "get_email_challenge_service",
    "get_email_delivery_service",
    "get_password_service",
    "router",
]
