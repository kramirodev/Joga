"""Autorização de `platform_admin` por allowlist de user IDs."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.modules.identity.sessions import AuthenticatedSession


def require_platform_admin(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedSession:
    """Autoriza apenas IDs listados em JOGA_PLATFORM_ADMINS.

    Papel de organização (OWNER/OPERATOR) não concede administração de
    plataforma; a verificação é sempre server-side.
    """

    if str(current.user_id) not in settings.platform_admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden"},
        )
    return current


__all__ = ["require_platform_admin"]
