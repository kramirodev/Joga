"""Sessão do painel web: refresh em cookie HttpOnly e proteção CSRF."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import (
    UserSummary,
    get_account_service,
    get_device_service,
    get_session_service,
)
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
from app.modules.identity.devices import DeviceService
from app.modules.identity.events import (
    AUTH_LOGIN_COMPLETED,
    AUTH_LOGOUT,
    AUTH_REFRESH_REUSE_DETECTED,
    AUTH_REFRESH_ROTATED,
    AUTH_REGISTRATION_COMPLETED,
    record_security_event,
)
from app.modules.identity.models import User
from app.modules.identity.sessions import (
    InvalidRefreshToken,
    IssuedTokens,
    RefreshReuseDetected,
    SessionService,
)

router = APIRouter(prefix="/auth/web", tags=["web-auth"])

REFRESH_COOKIE_NAME = "joga_web_refresh"
CSRF_COOKIE_NAME = "joga_web_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
REFRESH_COOKIE_PATH = "/api/v1/auth/web"


class WebReceiptRequest(BaseModel):
    challenge_id: UUID
    device_name: str | None = Field(default=None, max_length=80)


class WebSessionResponse(BaseModel):
    access_token: str
    access_expires_at: datetime
    csrf_token: str
    user: UserSummary


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


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


def _session_response(
    response: Response,
    tokens: IssuedTokens,
    user: User,
    settings: Settings,
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
    )


@router.post(
    "/registration",
    status_code=status.HTTP_201_CREATED,
    response_model=WebSessionResponse,
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
    return _session_response(response, tokens, record, settings)


@router.post("/login", response_model=WebSessionResponse)
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
    return _session_response(response, tokens, record, settings)


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
        session.rollback()
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token")

    record_security_event(session, AUTH_REFRESH_ROTATED, user_id=user.id)
    session.commit()
    return _session_response(response, tokens, user, settings)


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
