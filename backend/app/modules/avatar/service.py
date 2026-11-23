"""Regras de persistência do avatar e importação temporária do Instagram."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.modules.avatar.instagram import (
    InstagramImporter,
    InstagramImportError,
)
from app.modules.avatar.models import UserAvatar
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.ratelimit.service import RateLimitExceeded, enforce
from app.modules.venues.storage import PhotoNotFound, PhotoStorage, PhotoStorageError

IMPORT_MODE_DISABLED = "instagram_import_disabled"
INSTAGRAM_IMPORT_MODE = "scrape"
INSTAGRAM_SOURCE = "instagram_scrape"

USER_RATE_LIMIT = 5
USER_RATE_WINDOW_SECONDS = 3600
IP_RATE_LIMIT = 20
IP_RATE_WINDOW_SECONDS = 86400


class AvatarError(Exception):
    """Erro base de avatar."""


class InstagramImportDisabled(AvatarError):
    """Flag desligada ou modo sem cliente disponível."""


class AvatarStorageUnavailable(AvatarError):
    """Falha no storage privado de avatar."""


@dataclass(frozen=True)
class AvatarView:
    user_id: uuid.UUID
    source: str
    storage_key: str | None
    content_type: str | None
    size_bytes: int | None
    width: int | None
    height: int | None
    source_url: str | None
    imported_at: datetime | None
    updated_at: datetime


def is_instagram_import_enabled(mode: str) -> bool:
    """``api`` fica reservado: sem cliente oficial, a rota responde desligada."""

    return mode == INSTAGRAM_IMPORT_MODE


def _view(row: UserAvatar) -> AvatarView:
    return AvatarView(
        user_id=row.user_id,
        source=row.source,
        storage_key=row.storage_key,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        width=row.width,
        height=row.height,
        source_url=row.source_url,
        imported_at=row.imported_at,
        updated_at=row.updated_at,
    )


def get_avatar(session: Session, user_id: uuid.UUID) -> AvatarView | None:
    row = session.get(UserAvatar, user_id)
    return _view(row) if row is not None else None


def avatar_username(source_url: str | None) -> str | None:
    """``username`` derivado da página pública guardada; nunca da CDN."""

    if not source_url:
        return None
    try:
        parts = urlsplit(source_url)
    except ValueError:
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    return segments[0] if len(segments) == 1 else None


def import_instagram_avatar(
    session: Session,
    *,
    user_id: uuid.UUID,
    url: str,
    importer: InstagramImporter,
    storage: PhotoStorage,
    ip_key: str | None,
    now: datetime | None = None,
) -> AvatarView:
    """Aplica rate limit, baixa, grava e substitui o avatar anterior.

    O chamador é responsável pelo commit/rollback. O arquivo novo é removido se
    a gravação no banco falhar; o arquivo antigo só é apagado depois do flush da
    linha nova para não deixar o perfil apontando para um arquivo inexistente.
    """

    moment = now or utcnow()
    try:
        enforce(
            session,
            scope="avatar_instagram_user",
            key=str(user_id),
            limit=USER_RATE_LIMIT,
            window_seconds=USER_RATE_WINDOW_SECONDS,
            now=moment,
        )
        if ip_key is not None:
            enforce(
                session,
                scope="avatar_instagram_ip",
                key=ip_key,
                limit=IP_RATE_LIMIT,
                window_seconds=IP_RATE_WINDOW_SECONDS,
                now=moment,
            )
    except RateLimitExceeded as exc:
        record_audit(
            session,
            actor_user_id=user_id,
            action="avatar.instagram_import",
            resource_type="user_avatar",
            resource_id=user_id,
            details={"outcome": "rate_limited", "code": "rate_limited"},
        )
        raise exc

    try:
        photo = importer.fetch(url)
    except InstagramImportError as exc:
        record_audit(
            session,
            actor_user_id=user_id,
            action="avatar.instagram_import",
            resource_type="user_avatar",
            resource_id=user_id,
            details={"outcome": "error", "code": exc.code},
        )
        raise

    try:
        new_key = storage.save(photo.data)
    except PhotoStorageError as exc:
        record_audit(
            session,
            actor_user_id=user_id,
            action="avatar.instagram_import",
            resource_type="user_avatar",
            resource_id=user_id,
            details={
                "outcome": "error",
                "code": "avatar_storage_unavailable",
            },
        )
        raise AvatarStorageUnavailable from exc

    row = session.get(UserAvatar, user_id)
    old_key = row.storage_key if row is not None else None
    try:
        if row is None:
            row = UserAvatar(user_id=user_id)
            session.add(row)
        row.source = INSTAGRAM_SOURCE
        row.source_url = photo.page_url
        row.storage_key = new_key
        row.content_type = photo.content_type
        row.size_bytes = len(photo.data)
        row.width = photo.width
        row.height = photo.height
        row.imported_at = moment
        row.updated_at = moment
        session.flush()
    except Exception:
        try:
            storage.delete(new_key)
        except PhotoStorageError:
            pass
        raise

    if old_key is not None and old_key != new_key:
        try:
            storage.delete(old_key)
        except PhotoStorageError:
            # A linha nova é a fonte da verdade; um arquivo órfão é preferível a
            # falhar a importação já persistida. A limpeza pode ser repetida.
            pass

    record_audit(
        session,
        actor_user_id=user_id,
        action="avatar.instagram_import",
        resource_type="user_avatar",
        resource_id=user_id,
        details={
            "outcome": "success",
            "username": photo.username,
            "width": photo.width,
            "height": photo.height,
            "size_bytes": len(photo.data),
        },
    )
    session.flush()
    return _view(row)


def delete_instagram_avatar(
    session: Session,
    *,
    user_id: uuid.UUID,
    storage: PhotoStorage,
) -> bool:
    """Remove só o avatar importado do próprio usuário. Idempotente."""

    row = session.get(UserAvatar, user_id)
    if row is None or row.source != INSTAGRAM_SOURCE:
        return False

    key = row.storage_key
    session.delete(row)
    session.flush()
    if key is not None:
        try:
            storage.delete(key)
        except PhotoStorageError:
            pass
    record_audit(
        session,
        actor_user_id=user_id,
        action="avatar.instagram_delete",
        resource_type="user_avatar",
        resource_id=user_id,
        details={"outcome": "success"},
    )
    session.flush()
    return True


def read_avatar_content(
    session: Session,
    *,
    user_id: uuid.UUID,
    storage: PhotoStorage,
) -> tuple[bytes, str] | None:
    """Conteúdo do avatar, ou ``None`` quando não existe foto persistida."""

    row = session.get(UserAvatar, user_id)
    if row is None or row.storage_key is None:
        return None
    try:
        data = storage.read(row.storage_key)
    except PhotoNotFound:
        return None
    except PhotoStorageError as exc:
        raise AvatarStorageUnavailable from exc
    return data, row.content_type or "image/jpeg"


__all__ = [
    "AvatarError",
    "AvatarStorageUnavailable",
    "AvatarView",
    "InstagramImportDisabled",
    "avatar_username",
    "delete_instagram_avatar",
    "get_avatar",
    "import_instagram_avatar",
    "is_instagram_import_enabled",
    "read_avatar_content",
]
