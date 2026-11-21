"""CPF: validação, cifra AES-256-GCM, hash de unicidade e máscara.

O CPF é dado pessoal e nunca circula em claro fora da memória da requisição.
O ciphertext é ``nonce(12) || ciphertext || tag(16)`` e usa o ``user_id`` como
AAD: copiar o valor de um usuário para outro não decifra.

A chave de cifra vive apenas em configuração (``JOGA_CPF_KEY``/
``JOGA_CPF_KEY_ID``), nunca no banco, no Git, no bundle ou em log. Para rotação,
a chave anterior fica em ``JOGA_CPF_PREVIOUS_KEYS`` e o ciphertext guarda o
``cpf_key_id`` usado.

A unicidade por conta usa HMAC-SHA256 do CPF normalizado (ADR 0065). O segredo
é o ``JOGA_PHONE_HASH_SECRET``, já exigido fora do ambiente local, com o rótulo
``cpf`` para separar domínios. Não usamos a chave de cifra porque a rotação
dela mudaria todos os hashes; o hash precisa ser estável.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings

CPF_DIGITS = re.compile(r"\D")
KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16

_FIRST_WEIGHTS = tuple(range(10, 1, -1))
_SECOND_WEIGHTS = tuple(range(11, 1, -1))


class CpfError(ValueError):
    """Erro base de CPF; mensagens nunca incluem o valor recebido."""


class InvalidCpf(CpfError):
    """CPF fora do formato ou com dígitos verificadores inválidos."""


class CpfKeyUnavailable(CpfError):
    """Chave ausente ou inválida para a operação de cifra."""


class CpfDecryptionError(CpfError):
    """Ciphertext corrompido, de outra chave ou vinculado a outro usuário."""


class CpfAlreadyRegistered(CpfError):
    """CPF já vinculado a outra conta; nenhuma conta é escolhida pelo sistema."""


def normalize_cpf(value: str) -> str:
    """Remove formatação e valida os 11 dígitos e os verificadores."""
    if not isinstance(value, str):
        raise InvalidCpf("CPF deve ser texto")
    digits = CPF_DIGITS.sub("", value.strip())
    if len(digits) != 11:
        raise InvalidCpf("CPF deve ter 11 dígitos")
    if len(set(digits)) == 1:
        raise InvalidCpf("CPF inválido")
    if digits != _with_check_digits(digits[:9]):
        raise InvalidCpf("CPF inválido")
    return digits


def _check_digit(digits: str, weights: tuple[int, ...]) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights, strict=True))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def _with_check_digits(base: str) -> str:
    first = _check_digit(base, _FIRST_WEIGHTS)
    return base + first + _check_digit(base + first, _SECOND_WEIGHTS)


def mask_cpf(last2: str | None) -> str | None:
    """Exibição permitida ao jogador; nunca revela os nove primeiros dígitos."""
    if last2 is None or len(last2) != 2 or not last2.isdigit():
        return None
    return f"***.***.***-{last2}"


def hash_cpf(cpf: str, settings: Settings) -> str:
    """HMAC-SHA256 estável do CPF normalizado, usado só para unicidade.

    O rótulo ``cpf:`` separa este uso do hash de telefone/OTP que compartilha o
    mesmo segredo. O resultado nunca é devolvido em resposta nem registrado em
    log; ele existe apenas para o índice único parcial.
    """
    normalized = normalize_cpf(cpf)
    secret = settings.phone_hash_secret.get_secret_value()
    message = f"cpf:{normalized}".encode("ascii")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _decode_key(value: str) -> bytes:
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CpfKeyUnavailable("chave de CPF inválida") from exc
    if len(raw) != KEY_BYTES:
        raise CpfKeyUnavailable("chave de CPF deve ter 32 bytes")
    if raw == b"\x00" * KEY_BYTES:
        raise CpfKeyUnavailable("chave de CPF não pode ser o placeholder")
    return raw


def _key_for(key_id: str, settings: Settings) -> bytes:
    if settings.cpf_key_id == key_id and settings.cpf_key is not None:
        return _decode_key(settings.cpf_key.get_secret_value())
    previous = settings.cpf_previous_keys.get(key_id)
    if previous is not None:
        return _decode_key(previous.get_secret_value())
    raise CpfKeyUnavailable("chave de CPF desconhecida")


def _aad(user_id: uuid.UUID) -> bytes:
    return user_id.bytes


def encrypt_cpf(cpf: str, user_id: uuid.UUID, settings: Settings) -> tuple[bytes, str, str]:
    """Cifra o CPF e devolve ``(ciphertext, key_id, last2)``."""
    if settings.cpf_key is None or not settings.cpf_key_id:
        raise CpfKeyUnavailable("chave de CPF não configurada")
    normalized = normalize_cpf(cpf)
    key = _decode_key(settings.cpf_key.get_secret_value())
    nonce = _nonce()
    ciphertext = AESGCM(key).encrypt(nonce, normalized.encode("ascii"), _aad(user_id))
    return nonce + ciphertext, settings.cpf_key_id, normalized[-2:]


def decrypt_cpf(
    ciphertext: bytes | None,
    user_id: uuid.UUID,
    key_id: str | None,
    settings: Settings,
) -> str:
    """Decifra somente com a chave correta e o mesmo ``user_id`` (AAD)."""
    if ciphertext is None or not key_id:
        raise CpfDecryptionError("CPF não cadastrado")
    if len(ciphertext) < NONCE_BYTES + TAG_BYTES:
        raise CpfDecryptionError("CPF cifrado inválido")
    key = _key_for(key_id, settings)
    nonce, payload = ciphertext[:NONCE_BYTES], ciphertext[NONCE_BYTES:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, payload, _aad(user_id))
    except InvalidTag as exc:
        raise CpfDecryptionError("CPF cifrado inválido") from exc
    return plaintext.decode("ascii")


def _nonce() -> bytes:
    return secrets.token_bytes(NONCE_BYTES)
