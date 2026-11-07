"""Testes unitários de validação e reencode de fotos de quadra (Fase 12A)."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.modules.venues.photos import InvalidPhoto, process_photo


def image_bytes(
    *,
    image_format: str = "PNG",
    size: tuple[int, int] = (800, 600),
    color: tuple[int, int, int] = (20, 120, 200),
    exif: Image.Exif | None = None,
) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", size, color)
    if exif is None:
        image.save(output, format=image_format)
    else:
        image.save(output, format=image_format, exif=exif)
    return output.getvalue()


def process(raw: bytes, **overrides: int):  # noqa: ANN201
    settings = {
        "max_bytes": 5_000_000,
        "max_pixels": 40_000_000,
        "max_dimension": 4000,
        "min_dimension": 200,
        "output_max_dimension": 2000,
    }
    settings.update(overrides)
    return process_photo(raw, **settings)  # type: ignore[arg-type]


def test_valid_png_is_reencoded_as_jpeg_without_metadata() -> None:
    exif = Image.Exif()
    exif[271] = "Camera de teste"
    raw = image_bytes(image_format="JPEG", exif=exif)

    processed = process(raw)

    assert processed.content_type == "image/jpeg"
    assert processed.width == 800
    assert processed.height == 600
    with Image.open(BytesIO(processed.data)) as result:
        assert result.format == "JPEG"
        assert not result.getexif()
    assert b"Camera de teste" not in processed.data


def test_large_image_is_resized_to_output_limit() -> None:
    processed = process(image_bytes(size=(3000, 2000)))

    assert processed.width == 2000
    assert processed.height == 1333


def test_invalid_bytes_are_rejected() -> None:
    with pytest.raises(InvalidPhoto):
        process(b"isto nao e uma imagem")


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(InvalidPhoto):
        process(image_bytes(image_format="GIF"))


def test_size_limits_are_rejected() -> None:
    with pytest.raises(InvalidPhoto):
        process(image_bytes(), max_bytes=10)


def test_dimension_limits_are_rejected() -> None:
    with pytest.raises(InvalidPhoto):
        process(image_bytes(size=(100, 100)), min_dimension=200)
    with pytest.raises(InvalidPhoto):
        process(image_bytes(size=(500, 500)), max_dimension=400)
