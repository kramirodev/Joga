"""Serviço fiscal: intenção e resultado da nota do estabelecimento (ADR 0049)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.fiscal.models import FiscalDocument
from app.modules.identity.clock import utcnow

_CNPJ_DIGITS = re.compile(r"\D")


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
    settings: Settings | None = None,
) -> FiscalDocument | None:
    """Registra que a reserva precisa de nota da quadra contra o jogador.

    - ``disabled``: não faz nada e devolve ``None``.
    - ``placeholder``: grava ``pending_manual``, sem chamada externa.
    - ``provider``: impossível, a configuração recusa o boot.

    Idempotente por ``booking_id``: a segunda chamada devolve o registro existente.
    """
    resolved = settings or get_settings()
    if resolved.fiscal_mode == "disabled":
        return None
    if amount_cents < 0:
        raise ValueError("Valor do documento fiscal não pode ser negativo")

    existing = session.scalar(
        select(FiscalDocument).where(FiscalDocument.booking_id == booking_id)
    )
    if existing is not None:
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
    return document


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
