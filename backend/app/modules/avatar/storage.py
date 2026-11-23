"""Storage privado dos avatares, separado das fotos de quadra."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.modules.venues.storage import LocalPhotoStorage, PhotoStorage


def get_avatar_storage() -> PhotoStorage:
    """Raiz privada própria, fora de qualquer diretório estático."""

    return LocalPhotoStorage(Path(get_settings().media_root) / "avatars")


__all__ = ["get_avatar_storage"]
