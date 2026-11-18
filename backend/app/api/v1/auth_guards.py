"""Dependências de flag de fase da autenticação (ADR 0050).

As flags falham no boot quando a combinação é inválida. Em runtime, a rota
indisponível responde de forma estável para o app e o painel não a oferecerem.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings


def _forbidden(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": code})


def require_email_auth_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.auth_email_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "email_auth_disabled"},
        )


def require_phone_auth_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.auth_phone_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "phone_auth_disabled"},
        )


def require_phone_registration_allowed(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.signup_mode == "closed":
        raise _forbidden("signup_closed")
    if not settings.allow_phone_registration:
        raise _forbidden("phone_registration_disabled")


def require_email_registration_allowed(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.signup_mode == "closed":
        raise _forbidden("signup_closed")
    if not settings.allow_email_registration:
        raise _forbidden("email_registration_disabled")


__all__ = [
    "require_email_auth_enabled",
    "require_email_registration_allowed",
    "require_phone_auth_enabled",
    "require_phone_registration_allowed",
]
