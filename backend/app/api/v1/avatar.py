"""Endpoints do avatar do jogador (importação temporária do Instagram)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.request_context import request_ip_hash
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.avatar.instagram import (
    InstagramImporter,
    InstagramImportError,
)
from app.modules.avatar.service import (
    IMPORT_MODE_DISABLED,
    AvatarStorageUnavailable,
    AvatarView,
    avatar_username,
    delete_instagram_avatar,
    get_avatar,
    import_instagram_avatar,
    is_instagram_import_enabled,
    read_avatar_content,
)
from app.modules.avatar.storage import get_avatar_storage
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.venues.storage import PhotoStorage

router = APIRouter(tags=["avatar"])

AVATAR_CACHE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Disposition": 'inline; filename="avatar.jpg"',
}

_STATUS_BY_CODE = {
    "invalid_instagram_url": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "instagram_profile_not_found": status.HTTP_404_NOT_FOUND,
    "instagram_profile_private": status.HTTP_409_CONFLICT,
    "image_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "invalid_instagram_image": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "instagram_unavailable": status.HTTP_502_BAD_GATEWAY,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
}


class InstagramImportRequest(BaseModel):
    # O limite real de tamanho/forma é do validador de URL, que responde
    # ``422 invalid_instagram_url`` em vez de erro genérico de schema.
    url: str = Field(min_length=1, max_length=2048)


class InstagramAvatarResponse(BaseModel):
    source: Literal["instagram"]
    avatar_url: str
    username: str


class AvatarMetadataResponse(BaseModel):
    source: str | None
    avatar_url: str | None
    username: str | None
    width: int | None
    height: int | None
    size_bytes: int | None
    updated_at: datetime | None


def get_instagram_importer() -> InstagramImporter:
    return InstagramImporter(timeout_seconds=8.0)


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _api_source(source: str) -> str:
    """Contrato público usa ``instagram``; o banco guarda ``instagram_scrape``."""

    return "instagram" if source == "instagram_scrape" else source


def _avatar_url(view: AvatarView) -> str | None:
    if view.storage_key is None:
        return None
    return "/api/v1/me/avatar/content"


@router.post("/me/avatar/instagram", response_model=InstagramAvatarResponse)
def import_my_instagram_avatar(
    payload: InstagramImportRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[PhotoStorage, Depends(get_avatar_storage)],
    importer: Annotated[InstagramImporter, Depends(get_instagram_importer)],
) -> InstagramAvatarResponse:
    """Busca a foto pública do perfil informado. Falha nunca quebra o perfil."""

    if not is_instagram_import_enabled(settings.instagram_import_mode):
        # Sem rede, sem validação de URL e sem revelar se a flag existe.
        raise _error(status.HTTP_404_NOT_FOUND, IMPORT_MODE_DISABLED)

    try:
        view = import_instagram_avatar(
            session,
            user_id=current.user_id,
            url=payload.url,
            importer=importer,
            storage=storage,
            ip_key=request_ip_hash(request, settings),
        )
        session.commit()
    except RateLimitExceeded as exc:
        # Persiste o contador e a auditoria da tentativa recusada.
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    except InstagramImportError as exc:
        # Persiste a auditoria; o PNG/HTML nunca é gravado.
        session.commit()
        raise _error(_STATUS_BY_CODE.get(exc.code, status.HTTP_502_BAD_GATEWAY), exc.code) from None
    except AvatarStorageUnavailable:
        # Persiste contador e auditoria da tentativa que falhou no storage.
        session.commit()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "avatar_storage_unavailable",
        ) from None

    username = avatar_username(view.source_url)
    if username is None:
        raise _error(status.HTTP_502_BAD_GATEWAY, "instagram_unavailable")
    return InstagramAvatarResponse(
        source="instagram",
        avatar_url="/api/v1/me/avatar/content",
        username=username,
    )


@router.delete("/me/avatar/instagram", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_instagram_avatar(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_avatar_storage)],
) -> None:
    """Remove o vínculo e o arquivo. Idempotente e independente da flag."""

    delete_instagram_avatar(session, user_id=current.user_id, storage=storage)
    session.commit()


@router.get("/me/avatar", response_model=AvatarMetadataResponse)
def read_my_avatar(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> AvatarMetadataResponse:
    """Metadados do avatar; nunca expõe ``source_url`` nem a URL da CDN."""

    view = get_avatar(session, current.user_id)
    if view is None:
        return AvatarMetadataResponse(
            source=None,
            avatar_url=None,
            username=None,
            width=None,
            height=None,
            size_bytes=None,
            updated_at=None,
        )
    return AvatarMetadataResponse(
        source=_api_source(view.source),
        avatar_url=_avatar_url(view),
        username=avatar_username(view.source_url),
        width=view.width,
        height=view.height,
        size_bytes=view.size_bytes,
        updated_at=view.updated_at,
    )


@router.get("/me/avatar/content")
def read_my_avatar_content(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_avatar_storage)],
) -> Response:
    return _avatar_response(session, current.user_id, storage)


@router.get("/users/{user_id}/avatar/content")
def read_user_avatar_content(
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_avatar_storage)],
) -> Response:
    """Foto de outro jogador, autenticado e sem qualquer outro dado pessoal."""

    return _avatar_response(session, user_id, storage)


def _avatar_response(session: Session, user_id: UUID, storage: PhotoStorage) -> Response:
    try:
        result = read_avatar_content(session, user_id=user_id, storage=storage)
    except AvatarStorageUnavailable:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "avatar_storage_unavailable",
        ) from None
    if result is None:
        raise _error(status.HTTP_404_NOT_FOUND, "avatar_not_found")
    data, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        headers=AVATAR_CACHE_HEADERS,
    )
