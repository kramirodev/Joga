"""Endpoints de desafio e verificação de telefone (OTP)."""

from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.accounts import (
    AccountNotFound,
    AccountService,
    InvalidReceipt,
)
from app.modules.identity.accounts import (
    PhoneAlreadyRegistered as AccountPhoneAlreadyRegistered,
)
from app.modules.identity.clock import ensure_utc
from app.modules.identity.devices import DeviceNotFound, DeviceService
from app.modules.identity.events import (
    AUTH_DEVICE_REVOKED,
    AUTH_LOGIN_COMPLETED,
    AUTH_LOGOUT,
    AUTH_LOGOUT_ALL,
    AUTH_PHONE_CHANGE_COMPLETED,
    AUTH_PHONE_CHANGE_FAILED,
    AUTH_PHONE_CHANGE_REQUESTED,
    AUTH_REFRESH_REUSE_DETECTED,
    AUTH_REFRESH_ROTATED,
    AUTH_REGISTRATION_COMPLETED,
    OTP_CHALLENGE_REQUESTED,
    OTP_CHALLENGE_VERIFIED,
    OTP_RATE_LIMITED,
    OTP_VERIFICATION_FAILED,
    PASSKEY_AUTHENTICATED,
    PASSKEY_AUTHENTICATION_STARTED,
    PASSKEY_FAILED,
    PASSKEY_RATE_LIMITED,
    PASSKEY_REGISTERED,
    PASSKEY_REGISTRATION_STARTED,
    PASSKEY_REVOKED,
    record_security_event,
)
from app.modules.identity.models import Device, PasskeyCredential, User
from app.modules.identity.otp import (
    AttemptsExceeded,
    ChallengePurpose,
    ExpiredChallenge,
    HourlyLimitReached,
    InvalidChallenge,
    InvalidCode,
    IpLimitReached,
    OtpPolicy,
    PhoneChallengeService,
    ResendTooSoon,
)
from app.modules.identity.passkeys import (
    InvalidPasskeyChallenge,
    PasskeyAlreadyRegistered,
    PasskeyNotFound,
    PasskeyRateLimited,
    PasskeyService,
    PasskeyUserNotFound,
    PasskeyVerificationFailed,
)
from app.modules.identity.phone import InvalidPhoneNumber, hash_ip
from app.modules.identity.phone_change import (
    InvalidPhoneChange,
    PhoneChangeService,
    PhoneUnchanged,
)
from app.modules.identity.phone_change import (
    PhoneAlreadyRegistered as PhoneChangePhoneAlreadyRegistered,
)
from app.modules.identity.sessions import (
    AuthenticatedSession,
    InvalidAccessToken,
    InvalidRefreshToken,
    IssuedTokens,
    RefreshReuseDetected,
    SessionService,
)
from app.modules.identity.sms import RecordingSmsSender, SmsSender

SIMULATED_SMS_ENVIRONMENTS = {"local", "test", "development", "ci"}

router = APIRouter(prefix="/auth", tags=["auth"])


class ChallengeRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    purpose: Literal["registration", "login"]


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    expires_at: datetime
    resend_after_seconds: int


class VerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class VerifyResponse(BaseModel):
    challenge_id: UUID
    purpose: ChallengePurpose
    verified_at: datetime
    receipt_expires_at: datetime


class ReceiptRequest(BaseModel):
    challenge_id: UUID
    device_name: str | None = Field(default=None, max_length=80)
    platform: Literal["android", "ios", "web", "unknown"] = "unknown"


class UserSummary(BaseModel):
    id: UUID
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_at: datetime
    refresh_expires_at: datetime
    user: UserSummary


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class PhoneChangeRequest(BaseModel):
    new_phone: str = Field(min_length=7, max_length=20)


class PhoneChangeConfirmRequest(BaseModel):
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class PasskeyOptionsResponse(BaseModel):
    challenge_id: UUID
    public_key: dict[str, Any]
    expires_at: datetime


class PasskeyRegistrationVerifyRequest(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]
    name: str | None = Field(default=None, max_length=80)


class PasskeyRegistrationResponse(BaseModel):
    credential_id: str
    name: str | None


class PasskeyAuthenticationVerifyRequest(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]
    device_name: str | None = Field(default=None, max_length=80)
    platform: Literal["android", "ios", "web", "unknown"] = "unknown"


class DeviceSummary(BaseModel):
    id: UUID
    name: str | None
    platform: str
    created_at: datetime
    last_seen_at: datetime | None


class DeviceListResponse(BaseModel):
    devices: list[DeviceSummary]


class PasskeySummary(BaseModel):
    credential_id: str
    name: str | None
    created_at: datetime
    last_used_at: datetime | None


class PasskeyListResponse(BaseModel):
    credentials: list[PasskeySummary]


@lru_cache
def get_recording_sms_sender() -> RecordingSmsSender:
    """Adaptador simulado compartilhado no processo de desenvolvimento."""
    return RecordingSmsSender()


def get_sms_sender(settings: Annotated[Settings, Depends(get_settings)]) -> SmsSender:
    """Entrega SMS apenas por adaptador simulado; provedor real exige decisão."""
    if settings.environment.lower() not in SIMULATED_SMS_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "sms_provider_unavailable"},
        )
    return get_recording_sms_sender()


def get_challenge_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sender: Annotated[SmsSender, Depends(get_sms_sender)],
) -> PhoneChallengeService:
    policy = OtpPolicy(
        ttl_seconds=settings.otp_ttl_seconds,
        max_attempts=settings.otp_max_attempts,
        resend_cooldown_seconds=settings.otp_resend_cooldown_seconds,
        max_per_hour=settings.otp_max_per_hour,
        max_per_ip_per_hour=settings.otp_max_per_ip_per_hour,
        receipt_ttl_seconds=settings.otp_receipt_ttl_seconds,
        fixed_code=settings.dev_fixed_otp,
    )
    return PhoneChallengeService(
        session,
        sender,
        settings.phone_hash_secret.get_secret_value(),
        policy,
    )


def get_account_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountService:
    return AccountService(session, settings.otp_receipt_ttl_seconds)


def get_session_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionService:
    return SessionService(
        session,
        settings.token_hash_secret.get_secret_value(),
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_absolute_ttl_days=settings.refresh_absolute_ttl_days,
        refresh_idle_ttl_days=settings.refresh_idle_ttl_days,
    )


def get_phone_change_service(
    session: Annotated[Session, Depends(get_session)],
    challenges: Annotated[PhoneChallengeService, Depends(get_challenge_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PhoneChangeService:
    return PhoneChangeService(
        session,
        challenges,
        settings.phone_hash_secret.get_secret_value(),
    )


def get_passkey_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasskeyService:
    return PasskeyService(
        session,
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        origins=settings.webauthn_origins,
        challenge_ttl_seconds=settings.passkey_challenge_ttl_seconds,
        max_per_ip_per_hour=settings.passkey_max_per_ip_per_hour,
    )


def get_device_service(
    session: Annotated[Session, Depends(get_session)],
) -> DeviceService:
    return DeviceService(session)


def _bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token", www_authenticate=True)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token", www_authenticate=True)
    return token


def get_current_session(
    token: Annotated[str, Depends(_bearer_token)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> AuthenticatedSession:
    try:
        return service.authenticate(token)
    except InvalidAccessToken:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token", www_authenticate=True) from None


def _token_response(tokens: IssuedTokens, user: UserSummary) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
        user=user,
    )


def _passkey_summary(item: PasskeyCredential) -> PasskeySummary:
    return PasskeySummary(
        credential_id=item.credential_id,
        name=item.name,
        created_at=ensure_utc(item.created_at),
        last_used_at=ensure_utc(item.last_used_at) if item.last_used_at else None,
    )


def _device_summary(item: Device) -> DeviceSummary:
    return DeviceSummary(
        id=item.id,
        name=item.name,
        platform=item.platform,
        created_at=ensure_utc(item.created_at),
        last_seen_at=ensure_utc(item.last_seen_at) if item.last_seen_at else None,
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


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ip_hash(request: Request, settings: Settings) -> str | None:
    ip = _request_ip(request)
    if ip is None:
        return None
    return hash_ip(ip, settings.phone_hash_secret.get_secret_value())


def _error(
    status_code: int,
    code: str,
    *,
    retry_after_seconds: int | None = None,
    www_authenticate: bool = False,
) -> HTTPException:
    headers: dict[str, str] = {}
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(retry_after_seconds)
    if www_authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    return HTTPException(
        status_code=status_code,
        detail={"code": code},
        headers=headers or None,
    )


@router.post(
    "/phone/challenges",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ChallengeResponse,
)
def request_phone_challenge(
    payload: ChallengeRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PhoneChallengeService, Depends(get_challenge_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChallengeResponse:
    """Cria um desafio. A resposta não revela se o telefone já tem conta."""
    ip_hash = _ip_hash(request, settings)

    try:
        issued = service.request(
            payload.phone,
            ChallengePurpose(payload.purpose),
            request_ip=_request_ip(request),
        )
    except InvalidPhoneNumber:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_phone") from None
    except ResendTooSoon as error:
        record_security_event(
            session,
            OTP_RATE_LIMITED,
            ip_hash=ip_hash,
            details={"operation": "request", "reason": "resend"},
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None
    except (HourlyLimitReached, IpLimitReached):
        record_security_event(
            session,
            OTP_RATE_LIMITED,
            ip_hash=ip_hash,
            details={"operation": "request", "reason": "hourly"},
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None

    record_security_event(
        session,
        OTP_CHALLENGE_REQUESTED,
        ip_hash=ip_hash,
        details={"purpose": payload.purpose},
    )
    session.commit()

    return ChallengeResponse(
        challenge_id=issued.challenge_id,
        expires_at=issued.expires_at,
        resend_after_seconds=issued.resend_after_seconds,
    )


@router.post(
    "/phone/challenges/{challenge_id}/verify",
    response_model=VerifyResponse,
)
def verify_phone_challenge(
    challenge_id: UUID,
    payload: VerifyRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PhoneChallengeService, Depends(get_challenge_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerifyResponse:
    """Valida o OTP e devolve um recibo de verificação de curta duração.

    O recibo é o próprio `challenge_id` consumido; o fluxo de conta/sessão deve
    checar `consumed_at` e a janela de validade antes de usá-lo.
    """
    ip_hash = _ip_hash(request, settings)

    try:
        verified = service.verify(challenge_id, payload.code)
    except InvalidChallenge:
        record_security_event(
            session,
            OTP_VERIFICATION_FAILED,
            ip_hash=ip_hash,
            details={"reason": "invalid"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_code_or_challenge") from None
    except ExpiredChallenge:
        record_security_event(
            session,
            OTP_VERIFICATION_FAILED,
            ip_hash=ip_hash,
            details={"reason": "expired"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_code_or_challenge") from None
    except AttemptsExceeded:
        record_security_event(
            session,
            OTP_VERIFICATION_FAILED,
            ip_hash=ip_hash,
            details={"reason": "attempts"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_code_or_challenge") from None
    except InvalidCode:
        record_security_event(
            session,
            OTP_VERIFICATION_FAILED,
            ip_hash=ip_hash,
            details={"reason": "code"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_code_or_challenge") from None

    record_security_event(
        session,
        OTP_CHALLENGE_VERIFIED,
        ip_hash=ip_hash,
        details={"purpose": verified.purpose.value},
    )
    session.commit()

    return VerifyResponse(
        challenge_id=verified.challenge_id,
        purpose=verified.purpose,
        verified_at=verified.verified_at,
        receipt_expires_at=verified.receipt_expires_at,
    )


@router.post(
    "/registration",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
)
def register_with_phone(
    payload: ReceiptRequest,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
) -> TokenResponse:
    """Consome um recibo de registro e cria conta + sessão."""
    try:
        user = accounts.register(payload.challenge_id)
    except InvalidReceipt:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_receipt") from None
    except AccountPhoneAlreadyRegistered:
        raise _error(status.HTTP_409_CONFLICT, "phone_already_registered") from None

    tokens = _issue_session(
        sessions,
        devices,
        user.id,
        device_name=payload.device_name,
        platform=payload.platform,
    )
    record_security_event(session, AUTH_REGISTRATION_COMPLETED, user_id=user.id)
    session.commit()

    return _token_response(tokens, UserSummary(id=user.id, status=user.status))


@router.post("/login", response_model=TokenResponse)
def login_with_phone(
    payload: ReceiptRequest,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
) -> TokenResponse:
    """Consome um recibo de login e cria uma sessão para a conta existente."""
    try:
        user = accounts.login(payload.challenge_id)
    except InvalidReceipt:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_receipt") from None
    except AccountNotFound:
        raise _error(status.HTTP_404_NOT_FOUND, "account_not_found") from None

    tokens = _issue_session(
        sessions,
        devices,
        user.id,
        device_name=payload.device_name,
        platform=payload.platform,
    )
    record_security_event(session, AUTH_LOGIN_COMPLETED, user_id=user.id)
    session.commit()

    return _token_response(tokens, UserSummary(id=user.id, status=user.status))


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    payload: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> TokenResponse:
    """Rotaciona o refresh; reutilização revoga a família da sessão."""
    try:
        tokens = sessions.rotate(payload.refresh_token)
    except RefreshReuseDetected as error:
        record_security_event(
            session,
            AUTH_REFRESH_REUSE_DETECTED,
            user_id=error.user_id,
        )
        session.commit()
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "refresh_reuse_detected",
            www_authenticate=True,
        ) from None
    except InvalidRefreshToken:
        session.commit()
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_refresh_token",
            www_authenticate=True,
        ) from None

    user = session.get(User, tokens.user_id)
    if user is None or user.status != "active":
        session.rollback()
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_refresh_token",
            www_authenticate=True,
        ) from None

    record_security_event(session, AUTH_REFRESH_ROTATED, user_id=user.id)
    session.commit()

    return _token_response(tokens, UserSummary(id=user.id, status=user.status))


@router.get("/me", response_model=UserSummary)
def me(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> UserSummary:
    """Retorna a conta da sessão autenticada."""
    user = session.get(User, current.user_id)
    if user is None or user.status != "active":
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_token",
            www_authenticate=True,
        )
    return UserSummary(id=user.id, status=user.status)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """Revoga a sessão atual."""
    sessions.revoke_session(current.session_id)
    record_security_event(session, AUTH_LOGOUT, user_id=current.user_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """Revoga todas as sessões ativas do usuário."""
    revoked = sessions.revoke_all(current.user_id)
    record_security_event(
        session,
        AUTH_LOGOUT_ALL,
        user_id=current.user_id,
        details={"sessions": revoked},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/phone-change/challenges",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ChallengeResponse,
)
def request_phone_change(
    payload: PhoneChangeRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PhoneChangeService, Depends(get_phone_change_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChallengeResponse:
    """Cria desafio OTP no novo telefone de um usuário autenticado."""
    ip_hash = _ip_hash(request, settings)

    try:
        issued = service.request(
            current.user_id,
            payload.new_phone,
            request_ip=_request_ip(request),
        )
    except InvalidPhoneNumber:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_phone") from None
    except PhoneUnchanged:
        raise _error(status.HTTP_400_BAD_REQUEST, "phone_unchanged") from None
    except PhoneChangePhoneAlreadyRegistered:
        raise _error(status.HTTP_409_CONFLICT, "phone_already_registered") from None
    except ResendTooSoon as error:
        record_security_event(
            session,
            OTP_RATE_LIMITED,
            user_id=current.user_id,
            ip_hash=ip_hash,
            details={"operation": "phone_change", "reason": "resend"},
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=error.retry_after_seconds,
        ) from None
    except (HourlyLimitReached, IpLimitReached):
        record_security_event(
            session,
            OTP_RATE_LIMITED,
            user_id=current.user_id,
            ip_hash=ip_hash,
            details={"operation": "phone_change", "reason": "hourly"},
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None

    record_security_event(
        session,
        AUTH_PHONE_CHANGE_REQUESTED,
        user_id=current.user_id,
    )
    session.commit()

    return ChallengeResponse(
        challenge_id=issued.challenge_id,
        expires_at=issued.expires_at,
        resend_after_seconds=issued.resend_after_seconds,
    )


@router.post("/phone-change", status_code=status.HTTP_204_NO_CONTENT)
def confirm_phone_change(
    payload: PhoneChangeConfirmRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PhoneChangeService, Depends(get_phone_change_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """Verifica o OTP, troca o telefone e revoga todas as sessões."""
    try:
        service.confirm(current.user_id, payload.challenge_id, payload.code)
    except (
        InvalidPhoneChange,
        InvalidChallenge,
        ExpiredChallenge,
        AttemptsExceeded,
        InvalidCode,
    ):
        record_security_event(
            session,
            AUTH_PHONE_CHANGE_FAILED,
            user_id=current.user_id,
            details={"reason": "invalid"},
        )
        session.commit()
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_phone_change",
        ) from None
    except PhoneUnchanged:
        session.rollback()
        raise _error(status.HTTP_400_BAD_REQUEST, "phone_unchanged") from None
    except PhoneChangePhoneAlreadyRegistered:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "phone_already_registered") from None

    sessions.revoke_all(current.user_id, reason="phone_change")
    record_security_event(
        session,
        AUTH_PHONE_CHANGE_COMPLETED,
        user_id=current.user_id,
    )
    session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/passkeys/registration/options",
    response_model=PasskeyOptionsResponse,
)
def passkey_registration_options(
    http_request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasskeyOptionsResponse:
    """Gera opções para adicionar uma passkey à conta autenticada."""
    try:
        options = service.begin_registration(
            current.user_id,
            request_ip_hash=_ip_hash(http_request, settings),
        )
    except PasskeyRateLimited:
        record_security_event(
            session,
            PASSKEY_RATE_LIMITED,
            user_id=current.user_id,
        )
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None
    except PasskeyUserNotFound:
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_token",
            www_authenticate=True,
        ) from None

    record_security_event(
        session,
        PASSKEY_REGISTRATION_STARTED,
        user_id=current.user_id,
    )
    session.commit()

    return PasskeyOptionsResponse(
        challenge_id=options.challenge_id,
        public_key=options.public_key,
        expires_at=options.expires_at,
    )


@router.post(
    "/passkeys/registration/verify",
    status_code=status.HTTP_201_CREATED,
    response_model=PasskeyRegistrationResponse,
)
def passkey_registration_verify(
    payload: PasskeyRegistrationVerifyRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
) -> PasskeyRegistrationResponse:
    """Verifica a atestação e adiciona a credencial."""
    try:
        result = service.finish_registration(
            current.user_id,
            payload.challenge_id,
            payload.credential,
            name=payload.name,
        )
    except (InvalidPasskeyChallenge, PasskeyVerificationFailed, PasskeyUserNotFound):
        record_security_event(
            session,
            PASSKEY_FAILED,
            user_id=current.user_id,
            details={"operation": "registration"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_passkey") from None
    except PasskeyAlreadyRegistered:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT,
            "passkey_already_registered",
        ) from None

    record_security_event(
        session,
        PASSKEY_REGISTERED,
        user_id=current.user_id,
    )
    session.commit()

    return PasskeyRegistrationResponse(
        credential_id=result.credential_id,
        name=result.name,
    )


@router.post(
    "/passkeys/authentication/options",
    response_model=PasskeyOptionsResponse,
)
def passkey_authentication_options(
    http_request: Request,
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasskeyOptionsResponse:
    """Gera opções de login por passkey (credencial descobrível)."""
    try:
        options = service.begin_authentication(
            request_ip_hash=_ip_hash(http_request, settings),
        )
    except PasskeyRateLimited:
        record_security_event(session, PASSKEY_RATE_LIMITED)
        session.commit()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            retry_after_seconds=60,
        ) from None

    record_security_event(session, PASSKEY_AUTHENTICATION_STARTED)
    session.commit()

    return PasskeyOptionsResponse(
        challenge_id=options.challenge_id,
        public_key=options.public_key,
        expires_at=options.expires_at,
    )


@router.post(
    "/passkeys/authentication/verify",
    response_model=TokenResponse,
)
def passkey_authentication_verify(
    payload: PasskeyAuthenticationVerifyRequest,
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
) -> TokenResponse:
    """Verifica a asserção e emite uma sessão para a conta da credencial."""
    try:
        authenticated = service.finish_authentication(
            payload.challenge_id,
            payload.credential,
        )
    except (
        InvalidPasskeyChallenge,
        PasskeyVerificationFailed,
        PasskeyUserNotFound,
        PasskeyNotFound,
    ):
        record_security_event(
            session,
            PASSKEY_FAILED,
            details={"operation": "authentication"},
        )
        session.commit()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_passkey") from None

    user = session.get(User, authenticated.user_id)
    if user is None or user.status != "active":
        session.rollback()
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_passkey",
            www_authenticate=True,
        )

    tokens = _issue_session(
        sessions,
        devices,
        user.id,
        device_name=payload.device_name,
        platform=payload.platform,
    )
    record_security_event(session, PASSKEY_AUTHENTICATED, user_id=user.id)
    session.commit()

    return _token_response(tokens, UserSummary(id=user.id, status=user.status))


@router.get("/passkeys", response_model=PasskeyListResponse)
def list_passkeys(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
) -> PasskeyListResponse:
    """Lista as credenciais ativas da conta autenticada."""
    return PasskeyListResponse(
        credentials=[_passkey_summary(item) for item in service.list_credentials(current.user_id)]
    )


@router.delete("/passkeys/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_passkey(
    credential_id: str,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[PasskeyService, Depends(get_passkey_service)],
) -> Response:
    """Revoga uma credencial da própria conta."""
    try:
        service.revoke_credential(current.user_id, credential_id)
    except PasskeyNotFound:
        raise _error(status.HTTP_404_NOT_FOUND, "passkey_not_found") from None

    record_security_event(
        session,
        PASSKEY_REVOKED,
        user_id=current.user_id,
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices", response_model=DeviceListResponse)
def list_devices(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceListResponse:
    """Lista os dispositivos ativos da conta."""
    return DeviceListResponse(
        devices=[_device_summary(item) for item in service.list(current.user_id)]
    )


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    device_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> Response:
    """Revoga um dispositivo e todas as sessões vinculadas a ele."""
    try:
        service.revoke(current.user_id, device_id)
    except DeviceNotFound:
        raise _error(status.HTTP_404_NOT_FOUND, "device_not_found") from None

    record_security_event(
        session,
        AUTH_DEVICE_REVOKED,
        user_id=current.user_id,
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
