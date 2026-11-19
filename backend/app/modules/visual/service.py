"""Validação e leitura/escrita da identidade visual (ADR 0029/0043)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.visual.models import (
    VISUAL_KINDS,
    UserVisualIdentity,
    UserVisualUnlock,
    VisualCatalogItem,
)
from app.modules.visual.seed import default_identity_keys

VISUAL_CATALOG_VERSION = 1
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
PUBLIC_SLOTS = ("icon", "frame", "accent", "badge")
IDENTITY_SLOTS = ("icon", "frame", "accent", "entry", "emote", "badge")


class VisualError(Exception):
    """Erro base de identidade visual."""


class InvalidVisualItem(VisualError):
    """Chave inexistente, inativa ou de outro tipo."""


class VisualItemLocked(VisualError):
    """Item válido, mas não desbloqueado para o jogador."""


@dataclass(frozen=True)
class IdentityView:
    user_id: uuid.UUID
    icon_key: str | None
    frame_key: str | None
    accent_key: str | None
    entry_key: str | None
    emote_key: str | None
    badge_key: str | None
    catalog_version: int


def _validate_key_shape(key: str) -> str:
    normalized = key.strip().lower()
    if not KEY_PATTERN.fullmatch(normalized):
        raise InvalidVisualItem
    return normalized


def _validate_item(
    session: Session,
    *,
    user_id: uuid.UUID,
    key: str,
    kind: str,
) -> VisualCatalogItem:
    if kind not in VISUAL_KINDS:
        raise InvalidVisualItem
    normalized = _validate_key_shape(key)
    item = session.scalar(select(VisualCatalogItem).where(VisualCatalogItem.key == normalized))
    if item is None or not item.active or item.kind != kind:
        raise InvalidVisualItem
    if item.unlock_state != "free":
        unlocked = session.scalar(
            select(UserVisualUnlock.id).where(
                UserVisualUnlock.user_id == user_id,
                UserVisualUnlock.item_id == item.id,
            )
        )
        if unlocked is None:
            raise VisualItemLocked
    return item


def _identity_view(row: UserVisualIdentity) -> IdentityView:
    return IdentityView(
        user_id=row.user_id,
        icon_key=row.icon_key,
        frame_key=row.frame_key,
        accent_key=row.accent_key,
        entry_key=row.entry_key,
        emote_key=row.emote_key,
        badge_key=row.badge_key,
        catalog_version=row.catalog_version,
    )


def get_identity(session: Session, user_id: uuid.UUID) -> IdentityView:
    """Identidade equipada ou o baseline gratuito quando ainda não há escolha."""

    row = session.get(UserVisualIdentity, user_id)
    if row is not None:
        return _identity_view(row)
    defaults = default_identity_keys(session)
    return IdentityView(
        user_id=user_id,
        icon_key=defaults["icon"],
        frame_key=defaults["frame"],
        accent_key=defaults["accent"],
        entry_key=defaults["entry"],
        emote_key=defaults["emote"],
        badge_key=defaults["badge"],
        catalog_version=VISUAL_CATALOG_VERSION,
    )


def set_identity(
    session: Session,
    user_id: uuid.UUID,
    keys: Mapping[str, str],
) -> IdentityView:
    """Substitui os seis slots após validar item ativo e desbloqueio."""

    if set(keys) != set(IDENTITY_SLOTS):
        raise InvalidVisualItem
    resolved: dict[str, str] = {}
    for slot in IDENTITY_SLOTS:
        item = _validate_item(session, user_id=user_id, key=keys[slot], kind=slot)
        resolved[slot] = item.key

    row = session.get(UserVisualIdentity, user_id)
    if row is None:
        row = UserVisualIdentity(
            user_id=user_id,
            icon_key=resolved["icon"],
            frame_key=resolved["frame"],
            accent_key=resolved["accent"],
            entry_key=resolved["entry"],
            emote_key=resolved["emote"],
            badge_key=resolved["badge"],
            catalog_version=VISUAL_CATALOG_VERSION,
            updated_at=utcnow(),
        )
        session.add(row)
    else:
        row.icon_key = resolved["icon"]
        row.frame_key = resolved["frame"]
        row.accent_key = resolved["accent"]
        row.entry_key = resolved["entry"]
        row.emote_key = resolved["emote"]
        row.badge_key = resolved["badge"]
        row.catalog_version = VISUAL_CATALOG_VERSION
        row.updated_at = utcnow()
    session.flush()
    return _identity_view(row)


def public_identity(session: Session, user_id: uuid.UUID) -> dict[str, str | None]:
    """Quatro chaves públicas. Nunca inclui nome, e-mail, telefone ou CPF."""

    view = get_identity(session, user_id)
    return {f"{slot}_key": getattr(view, f"{slot}_key") for slot in PUBLIC_SLOTS}


def public_identities(
    session: Session, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, str | None]]:
    """Versão em lote para listas de participantes."""

    return {user_id: public_identity(session, user_id) for user_id in set(user_ids)}


def grant_unlock(
    session: Session,
    *,
    user_id: uuid.UUID,
    key: str,
    source: str = "xp",
) -> None:
    """Concede um desbloqueio; repetição é idempotente pela unique."""

    item = session.scalar(select(VisualCatalogItem).where(VisualCatalogItem.key == key))
    if item is None:
        raise InvalidVisualItem
    existing = session.scalar(
        select(UserVisualUnlock).where(
            UserVisualUnlock.user_id == user_id,
            UserVisualUnlock.item_id == item.id,
        )
    )
    if existing is not None:
        return
    session.add(UserVisualUnlock(user_id=user_id, item_id=item.id, source=source))


__all__ = [
    "IDENTITY_SLOTS",
    "IdentityView",
    "InvalidVisualItem",
    "PUBLIC_SLOTS",
    "VISUAL_CATALOG_VERSION",
    "VisualError",
    "VisualItemLocked",
    "get_identity",
    "grant_unlock",
    "public_identities",
    "public_identity",
    "set_identity",
]
