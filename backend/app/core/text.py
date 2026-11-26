"""Higiene e política de texto recebido do cliente.

O PostgreSQL recusa o byte NUL (``0x00``) em colunas ``text``; caracteres de
controle, invisíveis e de direção (bidi) também não têm uso legítimo em nome,
bio, descrição, motivo ou legenda. A política é rejeitar o payload (422) em vez
de remover silenciosamente, para que o cliente corrija a entrada e o dado nunca
chegue ao banco.

Há políticas distintas, aplicadas no schema Pydantic de entrada (fonte da
verdade no servidor):

- ``FreeText`` (uma linha): rejeita controle, inclusive C1/DEL, e invisíveis;
- ``MultilineText``: aceita ``\n`` como única quebra, normaliza ``\r\n``/``\r``
  para ``\n`` e rejeita os demais controles, bidi e zero-width;
- ``DisplayName``/``OptionalDisplayName``: nome de jogador canônico, com
  ``strip``, espaços colapsados, maiúsculas e alfabeto latino restrito;
- ``LatinName``: nome público (clã, organização, quadra) restrito a letras
  latinas, dígitos, espaço e ``. _ -``;
- ``AddressText``: endereço em alfabeto latino com pontuação usual.

Acentos e emoji são preservados nos textos livres (chat, bio, descrição). O
comprimento é sempre contado pelo número de code points (``len``), o mesmo
critério do ``max_length`` do Pydantic e das colunas ``String``.

A função ``escape_like`` protege filtros ``LIKE``/``ILIKE`` contra curingas
enviados pelo usuário.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

# NUL, controles C0, DEL e controles C1. Inclui CR/LF: texto de uma linha.
CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# Multilinha aceita apenas \n (0x0a); os demais controles continuam proibidos.
MULTILINE_CONTROL_PATTERN = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")
# Zero-width, marcas de direção (bidi), separadores e formatação invisível.
INVISIBLE_PATTERN = re.compile(
    r"[\u00ad\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2065\u2066-\u2069"
    r"\ufeff\ufff9-\ufffb]"
)

LIKE_ESCAPE = "\\"
DISPLAY_NAME_MIN_LENGTH = 3
DISPLAY_NAME_MAX_LENGTH = 60
CLAN_NAME_MIN_LENGTH = 3
CLAN_NAME_MAX_LENGTH = 40
WHITESPACE_PATTERN = re.compile(r"\s+")

# Alfabeto aceito em nomes públicos. O ponto, o hífen e o sublinhado são os
# únicos símbolos permitidos; não há emoji, CJK, árabe, hebraico ou homoglifos.
NAME_PUNCTUATION = frozenset(" ._-")
# Endereço usa pontuação brasileira usual (nº, apto., vírgulas, parênteses).
ADDRESS_PUNCTUATION = frozenset(" .,;:/-–—'’\"“”()#&+ºª°")


class UnsafeText(ValueError):
    """Texto com caractere de controle, invisível ou de direção (bidi)."""


class TextPolicyError(ValueError):
    """Texto fora da política; ``code`` e ``message`` vão na resposta 422."""

    code = "invalid_text"
    message = "Texto inválido."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code


class InvalidDisplayNameLength(TextPolicyError):
    """Nome de jogador vazio, curto demais ou longo demais."""

    code = "invalid_display_name_length"
    message = "O nome precisa ter de 3 a 60 caracteres."


class InvalidDisplayNameChars(TextPolicyError):
    """Nome de jogador com caractere fora do alfabeto permitido."""

    code = "invalid_display_name_chars"
    message = "Use apenas letras, números, espaço, ponto, hífen e sublinhado no nome."


class InvalidNameLength(TextPolicyError):
    """Nome público fora do tamanho permitido."""

    code = "invalid_name_length"
    message = "O nome está fora do tamanho permitido."


class InvalidNameChars(TextPolicyError):
    """Nome público com caractere fora do alfabeto permitido."""

    code = "invalid_name_chars"
    message = "Use apenas letras, números, espaço, ponto, hífen e sublinhado."


class InvalidAddressChars(TextPolicyError):
    """Endereço com caractere fora do alfabeto/pontuação permitidos."""

    code = "invalid_address_chars"
    message = "O endereço tem caracteres não permitidos."


def _is_latin_letter(char: str) -> bool:
    """Letra cujo nome Unicode é ``LATIN ...`` (inclui acentos pré-compostos)."""

    return unicodedata.category(char).startswith("L") and unicodedata.name(char, "").startswith(
        "LATIN "
    )


def _is_name_char(char: str) -> bool:
    return ("0" <= char <= "9") or char in NAME_PUNCTUATION or _is_latin_letter(char)


def _is_address_char(char: str) -> bool:
    return ("0" <= char <= "9") or char in ADDRESS_PUNCTUATION or _is_latin_letter(char)


def reject_control_characters(value: str | None) -> str | None:
    """Rejeita NUL, controles C0/C1 e DEL; mantém acentos, emoji e Unicode."""

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


def normalize_display_name(value: str | None) -> str | None:
    """Forma canônica do nome do jogador: ``strip``, espaços colapsados, upper.

    Acentos, emoji e o restante do Unicode são preservados. O resultado é
    limitado ao tamanho da coluna; nomes vazios ou só com espaços viram
    ``None``. Continua sendo a regra aplicada a valores já persistidos (o
    backfill histórico tem uma cópia própria). A validação de alfabeto de
    escritas novas fica em :func:`canonicalize_display_name`.
    """

    if value is None:
        return None
    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if not cleaned:
        return None
    canonical = cleaned.upper()[:DISPLAY_NAME_MAX_LENGTH].rstrip()
    return canonical or None


def canonicalize_display_name(value: str | None) -> str | None:
    """Aplica a política do nome do jogador em escritas novas.

    ``None`` e texto vazio/só espaços continuam significando "sem nome" (uma
    edição de perfil pode limpar o campo). Um nome informado precisa ter de 3 a
    60 caracteres depois de colapsar espaços e aplicar maiúsculas, usando só
    letras latinas (com acentos), dígitos, espaço, ponto, hífen e sublinhado.
    """

    if value is None:
        return None
    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if not cleaned:
        return None
    canonical = cleaned.upper()
    if not DISPLAY_NAME_MIN_LENGTH <= len(canonical) <= DISPLAY_NAME_MAX_LENGTH:
        raise InvalidDisplayNameLength
    if any(not _is_name_char(char) for char in canonical):
        raise InvalidDisplayNameChars
    return canonical


def canonicalize_clan_name(value: str) -> str:
    """Nome de clã: 3 a 40 caracteres, alfabeto latino, sem alterar maiúsculas."""

    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if not CLAN_NAME_MIN_LENGTH <= len(cleaned) <= CLAN_NAME_MAX_LENGTH:
        raise InvalidNameLength("O nome do clã precisa ter de 3 a 40 caracteres.")
    if any(not _is_name_char(char) for char in cleaned):
        raise InvalidNameChars(
            "Use apenas letras, números, espaço, ponto, hífen e sublinhado no nome do clã."
        )
    return cleaned


def canonicalize_organization_name(value: str) -> str:
    """Nome de organização: 2 a 120 caracteres em alfabeto latino."""

    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if not 2 <= len(cleaned) <= 120:
        raise InvalidNameLength("O nome da organização precisa ter de 2 a 120 caracteres.")
    if any(not _is_name_char(char) for char in cleaned):
        raise InvalidNameChars(
            "Use apenas letras, números, espaço, ponto, hífen e sublinhado no nome."
        )
    return cleaned


def canonicalize_venue_name(value: str) -> str:
    """Nome de quadra/arena: 1 a 120 caracteres em alfabeto latino."""

    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if not 1 <= len(cleaned) <= 120:
        raise InvalidNameLength("O nome precisa ter de 1 a 120 caracteres.")
    if any(not _is_name_char(char) for char in cleaned):
        raise InvalidNameChars(
            "Use apenas letras, números, espaço, ponto, hífen e sublinhado no nome."
        )
    return cleaned


def validate_latin_name(value: str) -> str:
    """Nome público sem limite próprio: só colapsa espaços e valida o alfabeto.

    Usado em campos cujo tamanho já é imposto por ``Field`` (nome de
    modalidade, formato, ícone do painel), evitando duplicar mensagens de
    comprimento diferentes da coluna.
    """

    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip())
    if any(not _is_name_char(char) for char in cleaned):
        raise InvalidNameChars
    return cleaned


def validate_address(value: str | None) -> str | None:
    """Endereço: alfabeto latino e pontuação usual, sem emoji/CJK/controle."""

    if value is None:
        return None
    if any(not _is_address_char(char) for char in value):
        raise InvalidAddressChars
    return value


def _latin_name_validator(
    validator: Callable[[str], str],
) -> Callable[[str | None], str | None]:
    """Adapta o canonicalizador obrigatório para o tipo opcional do Pydantic."""

    def validate(value: str | None) -> str | None:
        if value is None:
            return None
        return validator(value)

    return validate


FreeText = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
]
OptionalFreeText = Annotated[
    str | None,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
]
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
DisplayName = Annotated[
    str,
    AfterValidator(reject_display_name),
    AfterValidator(canonicalize_display_name),
]
OptionalDisplayName = Annotated[
    str | None,
    AfterValidator(reject_display_name),
    AfterValidator(canonicalize_display_name),
]
ClanName = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(canonicalize_clan_name),
]
LatinName = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(validate_latin_name),
]
OptionalLatinName = Annotated[
    str | None,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(_latin_name_validator(validate_latin_name)),
]
VenueName = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(canonicalize_venue_name),
]
OptionalVenueName = Annotated[
    str | None,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(_latin_name_validator(canonicalize_venue_name)),
]
OrganizationName = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(canonicalize_organization_name),
]
OptionalOrganizationName = Annotated[
    str | None,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(_latin_name_validator(canonicalize_organization_name)),
]
AddressText = Annotated[
    str,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(validate_address),
]
OptionalAddressText = Annotated[
    str | None,
    AfterValidator(reject_control_characters),
    AfterValidator(reject_invisible_characters),
    AfterValidator(validate_address),
]


__all__ = [
    "ADDRESS_PUNCTUATION",
    "CLAN_NAME_MAX_LENGTH",
    "CLAN_NAME_MIN_LENGTH",
    "CONTROL_PATTERN",
    "DISPLAY_NAME_MAX_LENGTH",
    "DISPLAY_NAME_MIN_LENGTH",
    "INVISIBLE_PATTERN",
    "LIKE_ESCAPE",
    "MULTILINE_CONTROL_PATTERN",
    "NAME_PUNCTUATION",
    "WHITESPACE_PATTERN",
    "AddressText",
    "ClanName",
    "DisplayName",
    "FreeText",
    "InvalidAddressChars",
    "InvalidDisplayNameChars",
    "InvalidDisplayNameLength",
    "InvalidNameChars",
    "InvalidNameLength",
    "LatinName",
    "MultilineText",
    "OptionalAddressText",
    "OptionalDisplayName",
    "OptionalFreeText",
    "OptionalLatinName",
    "OptionalMultilineText",
    "OptionalOrganizationName",
    "OptionalVenueName",
    "OrganizationName",
    "TextPolicyError",
    "UnsafeText",
    "VenueName",
    "canonicalize_clan_name",
    "canonicalize_display_name",
    "canonicalize_organization_name",
    "canonicalize_venue_name",
    "escape_like",
    "normalize_display_name",
    "normalize_newlines",
    "reject_control_characters",
    "reject_display_name",
    "reject_invisible_characters",
    "reject_multiline_characters",
    "validate_address",
    "validate_latin_name",
]
