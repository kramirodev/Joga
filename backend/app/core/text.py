"""Higiene de texto recebido do cliente.

O PostgreSQL recusa o byte NUL (``0x00``) em colunas ``text``; caracteres de
controle e invisíveis também não têm uso legítimo em nome, bio, descrição,
motivo ou legenda. A política é rejeitar o payload (422) em vez de remover
silenciosamente, para que o cliente corrija a entrada e o dado nunca chegue ao
banco. Acentos, emoji e texto Unicode normal continuam aceitos.

Há duas políticas:

- ``FreeText`` (uma linha): rejeita todo controle, inclusive CR/LF;
- ``MultilineText``: aceita ``\n`` como única quebra, normaliza ``\r\n``/``\r``
  para ``\n`` e rejeita os demais controles, bidi e zero-width.

Os tipos anotados são usados diretamente nos schemas Pydantic de entrada; a
função ``escape_like`` protege filtros ``LIKE``/``ILIKE`` contra curingas
enviados pelo usuário.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

# NUL, controles C0 e DEL. Inclui CR/LF: texto de uma linha.
CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
# Multilinha aceita apenas \n (0x0a); os demais controles continuam proibidos.
MULTILINE_CONTROL_PATTERN = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
# Zero-width, marcas de direção (bidi) e separadores invisíveis.
INVISIBLE_PATTERN = re.compile(
    r"[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)

LIKE_ESCAPE = "\\"


class UnsafeText(ValueError):
    """Texto com caractere de controle, invisível ou de direção (bidi)."""


def reject_control_characters(value: str | None) -> str | None:
    """Rejeita NUL, controles C0 e DEL; mantém acentos, emoji e Unicode."""

    if value is not None and CONTROL_PATTERN.search(value):
        raise UnsafeText("texto contém caracteres de controle")
    return value


def reject_invisible_characters(value: str | None) -> str | None:
    """Rejeita zero-width e marcas de direção usadas para personificação."""

    if value is not None and INVISIBLE_PATTERN.search(value):
        raise UnsafeText("texto contém caracteres invisíveis")
    return value


def reject_display_name(value: str | None) -> str | None:
    """Nome de exibição não aceita controle, CR/LF nem marcas invisíveis."""

    reject_control_characters(value)
    reject_invisible_characters(value)
    return value


def normalize_newlines(value: object) -> object:
    """Normaliza ``\r\n`` e ``\r`` para ``\n`` antes das demais validações."""

    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    return value


def reject_multiline_characters(value: str | None) -> str | None:
    """Rejeita tudo que não seja ``\n`` entre os controles, além de invisíveis."""

    if value is None:
        return None
    if MULTILINE_CONTROL_PATTERN.search(value) or INVISIBLE_PATTERN.search(value):
        raise UnsafeText("texto contém caracteres de controle")
    return value


def escape_like(value: str) -> str:
    """Escapa ``%``, ``_`` e a barra de escape para busca literal em LIKE."""

    return value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", "\\%").replace("_", "\\_")


FreeText = Annotated[str, AfterValidator(reject_control_characters)]
OptionalFreeText = Annotated[str | None, AfterValidator(reject_control_characters)]
MultilineText = Annotated[
    str,
    BeforeValidator(normalize_newlines),
    AfterValidator(reject_multiline_characters),
]
OptionalMultilineText = Annotated[
    str | None,
    BeforeValidator(normalize_newlines),
    AfterValidator(reject_multiline_characters),
]
DisplayName = Annotated[str, AfterValidator(reject_display_name)]
OptionalDisplayName = Annotated[str | None, AfterValidator(reject_display_name)]


__all__ = [
    "CONTROL_PATTERN",
    "INVISIBLE_PATTERN",
    "LIKE_ESCAPE",
    "MULTILINE_CONTROL_PATTERN",
    "DisplayName",
    "FreeText",
    "MultilineText",
    "OptionalDisplayName",
    "OptionalFreeText",
    "OptionalMultilineText",
    "UnsafeText",
    "escape_like",
    "normalize_newlines",
    "reject_control_characters",
    "reject_display_name",
    "reject_invisible_characters",
    "reject_multiline_characters",
]
