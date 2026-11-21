"""CPF único por conta (hash HMAC e índice único parcial)

Revision ID: 7a1b2c3d4e5f
Revises: 6f1a2b3c4d5e
Create Date: 2026-11-21 15:00:00.000000

ADR 0065. Adiciona ``user_profiles.cpf_hash`` (HMAC-SHA256 do CPF normalizado),
faz o backfill decifrando os CPFs existentes e cria o índice único parcial.
Duplicatas interrompem a migração com a lista de ``user_id``; nenhuma conta é
escolhida automaticamente e nenhum CPF/hash aparece na mensagem.

O hash usa ``JOGA_PHONE_HASH_SECRET`` com o rótulo ``cpf:``. Não usa a chave de
cifra para continuar estável quando ``JOGA_CPF_KEY`` rodar.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import uuid
from typing import Any

import sqlalchemy as sa
from alembic import op
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

revision: str = "7a1b2c3d4e5f"
down_revision: str | None = "6f1a2b3c4d5e"
branch_labels: str | None = None
depends_on: str | None = None

KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16
HASH_LABEL = "cpf:"


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("cpf_hash", sa.String(length=64), nullable=True),
    )
    _backfill_cpf_hash()
    op.drop_constraint("cpf_present_consistent", "user_profiles", type_="check")
    op.create_check_constraint(
        "cpf_present_consistent",
        "user_profiles",
        "(cpf_ciphertext IS NULL AND cpf_key_id IS NULL AND cpf_last2 IS NULL "
        "AND cpf_hash IS NULL) "
        "OR (cpf_ciphertext IS NOT NULL AND cpf_key_id IS NOT NULL "
        "AND cpf_last2 IS NOT NULL AND cpf_hash IS NOT NULL)",
    )
    op.create_index(
        "uq_user_profiles_cpf_hash",
        "user_profiles",
        ["cpf_hash"],
        unique=True,
        postgresql_where=sa.text("cpf_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_profiles_cpf_hash", table_name="user_profiles")
    op.drop_constraint("cpf_present_consistent", "user_profiles", type_="check")
    op.create_check_constraint(
        "cpf_present_consistent",
        "user_profiles",
        "(cpf_ciphertext IS NULL AND cpf_key_id IS NULL AND cpf_last2 IS NULL) "
        "OR (cpf_ciphertext IS NOT NULL AND cpf_key_id IS NOT NULL "
        "AND cpf_last2 IS NOT NULL)",
    )
    op.drop_column("user_profiles", "cpf_hash")


def _backfill_cpf_hash() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT user_id, cpf_ciphertext, cpf_key_id FROM user_profiles "
            "WHERE cpf_ciphertext IS NOT NULL"
        )
    ).all()
    if not rows:
        return

    settings = _settings()
    secret = settings.phone_hash_secret.get_secret_value().encode("utf-8")
    seen: dict[str, uuid.UUID] = {}
    updates: list[tuple[str, uuid.UUID]] = []
    duplicates: list[tuple[uuid.UUID, uuid.UUID]] = []

    for user_id_raw, ciphertext, key_id in rows:
        user_id = uuid.UUID(str(user_id_raw))
        try:
            plaintext = _decrypt_cpf(bytes(ciphertext), user_id, key_id, settings)
        except Exception as exc:  # noqa: BLE001 - mensagem estável sem PII
            raise RuntimeError(
                "cpf_hash backfill: não foi possível decifrar o CPF do usuário "
                f"{user_id}. Confira JOGA_CPF_KEY e JOGA_CPF_PREVIOUS_KEYS. "
                "Nenhuma conta foi alterada."
            ) from exc
        digest = hmac.new(
            secret,
            f"{HASH_LABEL}{plaintext}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        first = seen.get(digest)
        if first is not None:
            duplicates.append((first, user_id))
            continue
        seen[digest] = user_id
        updates.append((digest, user_id))

    if duplicates:
        pairs = ", ".join(f"{first} e {second}" for first, second in duplicates)
        raise RuntimeError(
            "cpf_hash backfill abortado: o mesmo CPF aparece em mais de uma conta "
            f"({pairs}). Decida manualmente qual conta mantém o CPF e remova ou "
            "altere as demais antes de aplicar a migração. Nenhuma conta foi alterada."
        )

    for digest, user_id in updates:
        connection.execute(
            sa.text("UPDATE user_profiles SET cpf_hash = :cpf_hash WHERE user_id = :user_id"),
            {"cpf_hash": digest, "user_id": user_id},
        )


def _settings() -> Any:
    settings = op.get_context().config.attributes.get("settings")
    if settings is None:
        raise RuntimeError(
            "cpf_hash backfill: configuração indisponível. Rode a migração pelo "
            "Alembic do projeto para carregar migrations/env.py."
        )
    return settings


def _decode_key(value: str) -> bytes:
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("cpf_hash backfill: chave de CPF inválida") from exc
    if len(raw) != KEY_BYTES:
        raise RuntimeError("cpf_hash backfill: chave de CPF deve ter 32 bytes")
    return raw


def _key_for(key_id: str, settings: Any) -> bytes:
    if settings.cpf_key is not None and settings.cpf_key_id == key_id:
        return _decode_key(settings.cpf_key.get_secret_value())
    previous = settings.cpf_previous_keys.get(key_id)
    if previous is not None:
        return _decode_key(previous.get_secret_value())
    raise RuntimeError(
        f"cpf_hash backfill: chave de CPF desconhecida ({key_id}). Confira JOGA_CPF_PREVIOUS_KEYS."
    )


def _decrypt_cpf(ciphertext: bytes, user_id: uuid.UUID, key_id: str | None, settings: Any) -> str:
    if not key_id:
        raise RuntimeError("cpf_hash backfill: ciphertext sem cpf_key_id")
    if len(ciphertext) < NONCE_BYTES + TAG_BYTES:
        raise RuntimeError("cpf_hash backfill: ciphertext de CPF inválido")
    key = _key_for(key_id, settings)
    plaintext = AESGCM(key).decrypt(
        ciphertext[:NONCE_BYTES],
        ciphertext[NONCE_BYTES:],
        user_id.bytes,
    )
    return plaintext.decode("ascii")
