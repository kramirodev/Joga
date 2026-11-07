"""Armazenamento privado de fotos de quadra.

O adaptador local é o padrão de desenvolvimento. Produção exige decisão de
storage de objetos, criptografia, backup e serving autorizado (ADR pendente).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

_KEY_PATTERN = re.compile(r"^[a-f0-9]{32}\.jpg$")


class PhotoStorageError(Exception):
    """Falha ao gravar, ler ou remover uma foto."""


class PhotoNotFound(PhotoStorageError):
    """Arquivo de foto inexistente no storage."""


class PhotoStorage(Protocol):
    """Contrato mínimo para armazenamento privado de fotos."""

    def save(self, data: bytes) -> str: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalPhotoStorage:
    """Armazenamento em disco local, fora de qualquer diretório estático."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, data: bytes) -> str:
        key = f"{uuid.uuid4().hex}.jpg"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_bytes(data)
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PhotoStorageError from exc
        return key

    def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise PhotoNotFound from exc
        except OSError as exc:
            raise PhotoStorageError from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise PhotoStorageError from exc

    def _path(self, key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(key):
            raise PhotoStorageError("chave de foto inválida")
        root = self.root.resolve()
        path = (root / key).resolve()
        if root not in path.parents:
            raise PhotoStorageError("caminho de foto fora do storage")
        return path


def get_photo_storage() -> PhotoStorage:
    return LocalPhotoStorage(Path(get_settings().media_root))
