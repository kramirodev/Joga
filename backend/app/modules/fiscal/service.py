"""Serviço fiscal: intenção e resultado da nota do estabelecimento (ADR 0049)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.fiscal.models import FiscalDocument, FiscalDocumentTaker
from app.modules.identity.clock import utcnow

_CNPJ_DIGITS = re.compile(r"\D")


@dataclass(frozen=True)
class TakerSnapshot:
    """Cota e CPF cifrado de um jogador no instante da intenção fiscal."""

    user_id: uuid.UUID
    amount_cents: int
    cpf_ciphertext: bytes | None = None
    cpf_key_id: str | None = None


def normalize_cnpj(value: str) -> str:
    """Normaliza o CNPJ para 14 dígitos. A validação de dígito é do cadastro."""
    digits = _CNPJ_DIGITS.sub("", value)
    if len(digits) != 14:
        raise ValueError("CNPJ do estabelecimento deve ter 14 dígitos")
    return digits


def record_document_intent(
    session: Session,
    *,
    booking_id: uuid.UUID,
    issuer_cnpj: str,
    taker_user_id: uuid.UUID,
    amount_cents: int,
    takers: Iterable[TakerSnapshot] = (),
    settings: Settings | None = None,
) -> FiscalDocument | None:
    """Registra que a reserva precisa de nota da quadra contra o jogador.

    - ``disabled``: não faz nada e devolve ``None``.
    - ``placeholder``: grava ``pending_manual``, sem chamada externa.
    - ``provider``: impossível, a configuração recusa o boot.

    Idempotente por ``booking_id``. Os tomadores por jogador são gravados uma
    única vez por ``(documento, usuário)``; repetir a chamada não duplica.
    """
    resolved = settings or get_settings()
    if resolved.fiscal_mode == "disabled":
        return None
    if amount_cents < 0:
        raise ValueError("Valor do documento fiscal não pode ser negativo")

    existing = session.scalar(select(FiscalDocument).where(FiscalDocument.booking_id == booking_id))
    if existing is not None:
        _add_missing_takers(session, existing, takers)
        return existing

    document = FiscalDocument(
        booking_id=booking_id,
        issuer_cnpj=normalize_cnpj(issuer_cnpj),
        taker_user_id=taker_user_id,
        amount_cents=amount_cents,
        status="pending_manual",
    )
    session.add(document)
    session.flush()
    _add_missing_takers(session, document, takers)
    return document


def _add_missing_takers(
    session: Session,
    document: FiscalDocument,
    takers: Iterable[TakerSnapshot],
) -> None:
    wanted = {taker.user_id: taker for taker in takers}
    if not wanted:
        return
    existing_users = set(
        session.scalars(
            select(FiscalDocumentTaker.user_id).where(
                FiscalDocumentTaker.fiscal_document_id == document.id
            )
        )
    )
    for user_id, taker in wanted.items():
        if user_id in existing_users:
            continue
        if taker.amount_cents < 0:
            raise ValueError("Valor do tomador não pode ser negativo")
        session.add(
            FiscalDocumentTaker(
                fiscal_document_id=document.id,
                user_id=user_id,
                amount_cents=taker.amount_cents,
                cpf_ciphertext=taker.cpf_ciphertext,
                cpf_key_id=taker.cpf_key_id,
            )
        )
    session.flush()


def mark_issued(
    session: Session,
    document: FiscalDocument,
    *,
    number: str,
    issued_at: datetime | None = None,
    provider_ref: str | None = None,
) -> FiscalDocument:
    """Fecha o registro com o número da nota emitida pela quadra."""
    if not number.strip():
        raise ValueError("Número do documento fiscal é obrigatório")
    document.status = "issued"
    document.number = number.strip()
    document.issued_at = issued_at or utcnow()
    if provider_ref is not None:
        document.provider_ref = provider_ref
    session.flush()
    return document


def mark_failed(session: Session, document: FiscalDocument) -> FiscalDocument:
    """Marca que o estabelecimento não emitiu a nota no prazo."""
    document.status = "failed"
    session.flush()
    return document
