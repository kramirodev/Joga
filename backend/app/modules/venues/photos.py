"""Validação e reencode seguro de fotos de quadra."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class InvalidPhoto(Exception):
    """Arquivo não é uma imagem aceita para foto de quadra."""


@dataclass(frozen=True)
class ProcessedPhoto:
    """Imagem normalizada, sem metadados, pronta para armazenamento privado."""

    data: bytes
    content_type: str
    width: int
    height: int


def process_photo(
    raw: bytes,
    *,
    max_bytes: int,
    max_pixels: int,
    max_dimension: int,
    min_dimension: int,
    output_max_dimension: int,
) -> ProcessedPhoto:
    """Valida, reencoda em JPEG e remove EXIF/metadados.

    O tipo declarado pelo cliente nunca é usado como prova. A validação real é
    feita pelo Pillow, seguida de reencode para eliminar polyglots e metadados.
    """

    if not raw:
        raise InvalidPhoto("arquivo vazio")
    if len(raw) > max_bytes:
        raise InvalidPhoto("arquivo acima do limite")

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
        raise InvalidPhoto("imagem inválida") from exc

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise InvalidPhoto("formato não permitido")
                width, height = image.size
                if width < min_dimension or height < min_dimension:
                    raise InvalidPhoto("dimensões abaixo do mínimo")
                if width > max_dimension or height > max_dimension:
                    raise InvalidPhoto("dimensões acima do máximo")
                if width * height > max_pixels:
                    raise InvalidPhoto("quantidade de pixels acima do limite")

                normalized = image.convert("RGB")
                normalized.thumbnail(
                    (output_max_dimension, output_max_dimension),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                normalized.save(
                    output,
                    format="JPEG",
                    quality=85,
                    optimize=True,
                    progressive=True,
                )
                return ProcessedPhoto(
                    data=output.getvalue(),
                    content_type="image/jpeg",
                    width=normalized.width,
                    height=normalized.height,
                )
    except InvalidPhoto:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidPhoto("imagem inválida") from exc
