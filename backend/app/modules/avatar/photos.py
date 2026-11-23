"""Validação e normalização da foto de avatar.

A foto importada é tratada como entrada externa não confiável: bytes mágicos,
decodificação real pelo Pillow, limite de pixels e reencode obrigatório para
JPEG 512×512. O reencode elimina EXIF, metadados e eventual conteúdo anexado
(polyglot) antes de qualquer gravação em storage privado.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIDE = 512
AVATAR_JPEG_QUALITY = 85
AVATAR_MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_MARK = b"WEBP"


class InvalidAvatarImage(Exception):
    """Bytes não são uma imagem JPEG/PNG/WebP válida para avatar."""


@dataclass(frozen=True)
class ProcessedAvatar:
    """JPEG quadrado, sem metadados, pronto para storage privado."""

    data: bytes
    content_type: str
    width: int
    height: int


def _has_allowed_magic(raw: bytes) -> bool:
    if raw.startswith(_JPEG_MAGIC):
        return True
    if raw.startswith(_PNG_MAGIC):
        return True
    return len(raw) >= 12 and raw.startswith(_WEBP_RIFF) and raw[8:12] == _WEBP_MARK


def process_avatar(raw: bytes, *, max_bytes: int) -> ProcessedAvatar:
    """Valida, recorta em 512×512 e reencoda em JPEG sem EXIF."""

    if not raw:
        raise InvalidAvatarImage("imagem vazia")
    if len(raw) > max_bytes:
        raise InvalidAvatarImage("imagem acima do limite")
    if not _has_allowed_magic(raw):
        raise InvalidAvatarImage("formato não permitido")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as probe:
                probe.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidAvatarImage("imagem inválida") from exc

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise InvalidAvatarImage("formato não permitido")
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise InvalidAvatarImage("dimensões inválidas")
                if width * height > AVATAR_MAX_PIXELS:
                    raise InvalidAvatarImage("quantidade de pixels acima do limite")

                normalized = ImageOps.fit(
                    image.convert("RGB"),
                    (AVATAR_SIDE, AVATAR_SIDE),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                output = BytesIO()
                # Não passar ``exif``/``icc_profile``: o padrão do Pillow já
                # grava um JPEG limpo, sem os metadados da origem.
                normalized.save(
                    output,
                    format="JPEG",
                    quality=AVATAR_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                return ProcessedAvatar(
                    data=output.getvalue(),
                    content_type="image/jpeg",
                    width=AVATAR_SIDE,
                    height=AVATAR_SIDE,
                )
    except InvalidAvatarImage:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidAvatarImage("imagem inválida") from exc
