"""Sessão do painel web: refresh em cookie HttpOnly e proteção CSRF."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import (
    UserSummary,
    get_account_service,
    get_device_service,
    get_session_service,
)
from app.api.v1.auth_guards import (
    require_email_auth_enabled,
    require_email_registration_allowed,
    require_phone_auth_enabled,
    require_phone_registration_allowed,
)
from app.api.v1.email_auth import (
    enforce_login_limits,
    get_email_account_service,
    get_email_delivery_service,
)
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.email.addresses import InvalidEmail, normalize_email
from app.modules.email.alerts import queue_security_alert
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.identity.accounts import (
    AccountNotFound,
    AccountService,
    InvalidReceipt,
)
from app.modules.identity.accounts import (
    PhoneAlreadyRegistered as AccountPhoneAlreadyRegistered,
)
from app.modules.identity.devices import DeviceService
from app.modules.identity.email_accounts import (
    EmailAccountService,
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidEmailReceipt,
)
from app.modules.identity.events import (
    AUTH_LOGIN_COMPLETED,
    AUTH_LOGOUT,
    AUTH_REFRESH_REUSE_DETECTED,
    AUTH_REFRESH_ROTATED,
    AUTH_REGISTRATION_COMPLETED,
    EMAIL_LOGIN_COMPLETED,
    EMAIL_LOGIN_FAILED,
    EMAIL_RATE_LIMITED,
    EMAIL_REGISTRATION_COMPLETED,
    record_security_event,
)
from app.modules.identity.models import User
from app.modules.identity.passwords import PasswordPolicyError
from app.modules.identity.phone import hash_ip
from app.modules.identity.sessions import (
    InvalidRefreshToken,
    IssuedTokens,
    RefreshReuseDetected,
    SessionService,
)
from app.modules.moderation.service import ModerationService
from app.modules.ratelimit.service import RateLimitExceeded

router = APIRouter(prefix="/auth/web", tags=["web-auth"])

REFRESH_COOKIE_NAME = "joga_web_refresh"
CSRF_COOKIE_NAME = "joga_web_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
REFRESH_COOKIE_PATH = "/api/v1/auth/web"


class WebReceiptRequest(BaseModel):
    challenge_id: UUID
    device_name: str | None = Field(default=None, max_length=80)


class WebEmailRegisterRequest(WebReceiptRequest):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=60)


class WebEmailLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    device_name: str | None = Field(default=None, max_length=80)


class WebSessionResponse(BaseModel):
    access_token: str
    access_expires_at: datetime
    csrf_token: str
    user: UserSummary
    capabilities: list[str]


def _error(
    status_code: int,
    code: str,
    *,
    retry_after_seconds: int | None = None,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after_seconds)} if retry_after_seconds is not None else None
    return HTTPException(status_code=status_code, detail={"code": code}, headers=headers)


def _issue_session(
    sessions: SessionService,
    devices: DeviceService,
    user_id: UUID,
    *,
    device_name: str | None,
) -> IssuedTokens:
    device_id = None
    if device_name:
        device_id = devices.register(user_id, device_name, "web").id
    return sessions.issue(user_id, device_id=device_id)


def _require_csrf(cookie: str | None, header: str | None) -> None:
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise _error(status.HTTP_403_FORBIDDEN, "csrf_failed")


def _set_session_cookies(
    response: Response,
    *,
    refresh_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    max_age = settings.refresh_absolute_ttl_days * 86_400
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.web_cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.web_cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.web_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=settings.web_cookie_secure,
        httponly=False,
        samesite="strict",
    )


def _capabilities(session: Session, user_id: UUID, settings: Settings) -> list[str]:
    capabilities: list[str] = []
    role = ModerationService(session).operator_role(user_id)
    if role is not None:
        capabilities.append("moderation.read")
        if role == "ADMIN":
            capabilities.append("moderation.manage")
    if str(user_id) in settings.platform_admin_ids:
        capabilities.append("platform.admin")
    return capabilities


def _session_response(
    response: Response,
    tokens: IssuedTokens,
    user: User,
    settings: Settings,
    capabilities: list[str],
) -> WebSessionResponse:
    csrf_token = secrets.token_urlsafe(32)
    _set_session_cookies(
        response,
        refresh_token=tokens.refresh_token,
        csrf_token=csrf_token,
        settings=settings,
    )
    return WebSessionResponse(
        access_token=tokens.access_token,
        access_expires_at=tokens.access_expires_at,
        csrf_token=csrf_token,
        user=UserSummary(id=user.id, status=user.status),
        capabilities=capabilities,
    )


@router.post(
    "/registration",
    status_code=status.HTTP_201_CREATED,
    response_model=WebSessionResponse,
    dependencies=[
        Depends(require_phone_auth_enabled),
        Depends(require_phone_registration_allowed),
    ],
)
def web_register(
    payload: WebReceiptRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebSessionResponse:
    """Cria conta pelo painel e devolve access em memória e refresh em cookie."""
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
    )
    record_security_event(session, AUTH_REGISTRATION_COMPLETED, user_id=user.id)
    session.commit()

    record = session.get(User, user.id)
    if record is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return _session_response(
        response,
        tokens,
        record,
        settings,
        _capabilities(session, record.id, settings),
    )


@router.post(
    "/login",
    response_model=WebSessionResponse,
    dependencies=[Depends(require_phone_auth_enabled)],
)
def web_login(
    payload: WebReceiptRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebSessionResponse:
    """Autentica uma conta existente e entrega a sessão do painel."""
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
    )
    record_security_event(session, AUTH_LOGIN_COMPLETED, user_id=user.id)
    session.commit()

    record = session.get(User, user.id)
    if record is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return _session_response(
        response,
        tokens,
        record,
        settings,
        _capabilities(session, record.id, settings),
    )


@router.post(
    "/email/registration",
    status_code=status.HTTP_201_CREATED,
    response_model=WebSessionResponse,
    dependencies=[
        Depends(require_email_auth_enabled),
        Depends(require_email_registration_allowed),
    ],
)
def web_register_email(
    payload: WebEmailRegisterRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebSessionResponse:
    """Cria conta por e-mail/senha e entrega a sessão do painel em cookies."""
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
    )
    try:
        welcome_email = normalize_email(payload.email)
    except InvalidEmail:  # pragma: no cover - já validado no serviço
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

    record = session.get(User, account.id)
    if record is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return _session_response(
        response,
        tokens,
        record,
        settings,
        _capabilities(session, record.id, settings),
    )


@router.post(
    "/email/login",
    response_model=WebSessionResponse,
    dependencies=[Depends(require_email_auth_enabled)],
)
def web_login_email(
    payload: WebEmailLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    accounts: Annotated[EmailAccountService, Depends(get_email_account_service)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    devices: Annotated[DeviceService, Depends(get_device_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebSessionResponse:
    """Autentica por e-mail + senha no painel, com rate limit e erro genérico."""
    request_ip = request.client.host if request.client else None
    ip_hash = (
        hash_ip(request_ip, settings.phone_hash_secret.get_secret_value()) if request_ip else None
    )
    try:
        normalized, _ = enforce_login_limits(
            session,
            settings,
            email=payload.email,
            request_ip=request_ip,
        )
    except InvalidEmail:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_email") from None
    except RateLimitExceeded as error:
        record_security_event(
            session,
            EMAIL_RATE_LIMITED,
            ip_hash=ip_hash,
            details={"operation": "web_login", "reason": "rate_limit"},
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
            details={"reason": "credentials", "surface": "web"},
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
    )
    if new_device:
        queue_security_alert(
            session,
            deliveries,
            user_id=account.id,
            reference=f"web-login:{uuid.uuid4()}",
            device_label=payload.device_name,
        )
    record_security_event(session, EMAIL_LOGIN_COMPLETED, user_id=account.id)
    session.commit()

    record = session.get(User, account.id)
    if record is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return _session_response(
        response,
        tokens,
        record,
        settings,
        _capabilities(session, record.id, settings),
    )


@router.post("/refresh", response_model=WebSessionResponse)
def web_refresh(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> WebSessionResponse:
    """Rotaciona a sessão web; exige o token CSRF de duplo envio."""
    _require_csrf(csrf_cookie, csrf_header)
    if refresh_token is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token")

    try:
        tokens = sessions.rotate(refresh_token)
    except RefreshReuseDetected as error:
        record_security_event(
            session,
            AUTH_REFRESH_REUSE_DETECTED,
            user_id=error.user_id,
        )
        session.commit()
        raise _error(status.HTTP_401_UNAUTHORIZED, "refresh_reuse_detected") from None
    except InvalidRefreshToken:
        session.commit()
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token") from None

    user = session.get(User, tokens.user_id)
    if user is None or user.status != "active":
        code = (
            "account_suspended"
            if user is not None and user.status == "suspended"
            else "invalid_refresh_token"
        )
        session.rollback()
        raise _error(status.HTTP_401_UNAUTHORIZED, code)

    record_security_event(session, AUTH_REFRESH_ROTATED, user_id=user.id)
    session.commit()
    return _session_response(
        response,
        tokens,
        user,
        settings,
        _capabilities(session, user.id, settings),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def web_logout(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> None:
    """Revoga a sessão web e remove os cookies, mesmo se já estiver expirada."""
    _require_csrf(csrf_cookie, csrf_header)
    user_id = (
        sessions.revoke_by_refresh(refresh_token, reason="web_logout")
        if refresh_token is not None
        else None
    )
    if user_id is not None:
        record_security_event(session, AUTH_LOGOUT, user_id=user_id)
    session.commit()
    _clear_session_cookies(response, settings)
