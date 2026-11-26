"""Hash e política de senha com Argon2id (ADR 0050).

A senha nunca é persistida em claro. O banco guarda apenas a string PHC do
Argon2id, que inclui salt, parâmetros e hash.

A senha é tratada como string exata: sem ``strip``, sem normalização Unicode.
Qualquer alfabeto imprimível é aceito (acentos, CJK, árabe, emoji), mas
controles C0/C1/DEL, zero-width e marcas bidi são rejeitados. Espaços internos
fazem parte da senha; espaços só nas pontas ou senha só de espaços são
rejeitados para evitar diferenças invisíveis entre cadastro e login.
"""

from __future__ import annotations

import re
import secrets
from functools import lru_cache
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type
from pydantic import AfterValidator

from app.core.text import INVISIBLE_PATTERN, TextPolicyError

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# NUL, controles C0/C1 e DEL nunca fazem parte de uma senha digitada.
PASSWORD_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")

# Parâmetros conservadores do beta: 64 MiB, 3 iterações, 4 lanes.
ARGON2_MEMORY_COST = 65_536
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

# Lista local, sem dependência paga. Comparação em minúsculas e sem espaços
# nas pontas. Não substitui um verificador de vazamentos; é a primeira barreira.
COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "123456789012",
        "abcdefghij",
        "abcd123456",
        "admin12345",
        "administrador",
        "amor123456",
        "brasil12345",
        "corinthians",
        "flamengo10",
        "futebol123",
        "joga123456",
        "jogador123",
        "mudar12345",
        "password10",
        "password123",
        "qwerty12345",
        "senha12345",
        "senha123456",
        "senhasegura",
        "trocarsenha",
        "vivaofutebol",
        "welcome1234",
        "xbox360vida",
    }
)

INVALID_PASSWORD_MESSAGE = "senha não atende à política"


class PasswordPolicyError(ValueError):
    """Senha fora da política; a API responde ``weak_password``."""


class InvalidPasswordChars(TextPolicyError):
    """Senha com controle/invisível; a API responde 422."""

    code = "invalid_password_chars"
    message = "A senha não pode conter caracteres invisíveis ou de controle."


class InvalidPasswordWhitespace(TextPolicyError):
    """Senha com espaço nas pontas ou composta só de espaços."""

    code = "invalid_password_spaces"
    message = "A senha não pode começar ou terminar com espaço."


def validate_password_characters(password: str) -> str:
    """Higiene de caracteres da senha, aplicada no schema (422).

    Não normaliza e não remove nada: o mesmo valor exato segue para o hash.
    """

    if PASSWORD_CONTROL_PATTERN.search(password) or INVISIBLE_PATTERN.search(password):
        raise InvalidPasswordChars
    if not password.strip() or password != password.strip():
        raise InvalidPasswordWhitespace
    return password


# Tipo de entrada compartilhado por cadastro, login, troca e reset de senha.
PasswordInput = Annotated[str, AfterValidator(validate_password_characters)]


def _build_hasher(
    *,
    memory_cost: int = ARGON2_MEMORY_COST,
    time_cost: int = ARGON2_TIME_COST,
    parallelism: int = ARGON2_PARALLELISM,
) -> PasswordHasher:
    return PasswordHasher(
        type=Type.ID,
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        hash_len=ARGON2_HASH_LEN,
        salt_len=ARGON2_SALT_LEN,
    )


DEFAULT_HASHER = _build_hasher()


@lru_cache(maxsize=1)
def _default_dummy_hash() -> str:
    """Hash descartável para igualar o custo de e-mail inexistente."""
    return DEFAULT_HASHER.hash(secrets.token_urlsafe(32))


class PasswordService:
    """Hash, verificação e política de senha."""

    def __init__(
        self,
        hasher: PasswordHasher | None = None,
        *,
        dummy_hash: str | None = None,
    ) -> None:
        self._hasher = hasher or DEFAULT_HASHER
        self._dummy_hash = dummy_hash or _default_dummy_hash()

    def validate(self, password: str, email: str) -> None:
        """Aplica mínimo/máximo, higiene, lista comum e igualdade com o e-mail."""
        if not isinstance(password, str):
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)
        if len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)
        if PASSWORD_CONTROL_PATTERN.search(password) or INVISIBLE_PATTERN.search(password):
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)
        if not password.strip() or password != password.strip():
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)

        lowered = password.casefold()
        normalized_email = email.casefold()
        local_part = normalized_email.rsplit("@", 1)[0]
        if lowered == normalized_email or lowered == local_part:
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)
        if password.strip().casefold() in COMMON_PASSWORDS:
            raise PasswordPolicyError(INVALID_PASSWORD_MESSAGE)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Compara em tempo constante; hash inválido nunca autentica."""
        try:
            return bool(self._hasher.verify(password_hash, password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        """Executa um verify descartável para nivelar o tempo de resposta."""
        self.verify(self._dummy_hash, password)

    def needs_rehash(self, password_hash: str) -> bool:
        """Indica se a credencial deve ser regravada com os parâmetros atuais."""
        try:
            return bool(self._hasher.check_needs_rehash(password_hash))
        except InvalidHashError:
            return True


__all__ = [
    "ARGON2_MEMORY_COST",
    "ARGON2_PARALLELISM",
    "ARGON2_TIME_COST",
    "COMMON_PASSWORDS",
    "INVALID_PASSWORD_MESSAGE",
    "InvalidPasswordChars",
    "InvalidPasswordWhitespace",
    "PASSWORD_CONTROL_PATTERN",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "PasswordInput",
    "PasswordPolicyError",
    "PasswordService",
    "validate_password_characters",
]
