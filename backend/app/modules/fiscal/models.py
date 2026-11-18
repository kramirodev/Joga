"""Registro de documentos fiscais de terceiros por reserva (ADR 0049 §3.8).

O backend **não emite** NFS-e. Ele registra que o estabelecimento deve emitir a
nota contra o jogador e guarda o que foi emitido, para que a cadeia documental do
modelo de intermediação seja verificável.

Em ``JOGA_FISCAL_MODE=placeholder`` nada é enviado a emissor externo: o registro
nasce como ``pending_manual`` e espera operação humana.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

FISCAL_DOCUMENT_STATUSES = ("pending_manual", "issued", "failed", "not_required")


class FiscalDocument(Base):
    """Nota do estabelecimento contra o jogador, ligada a uma reserva.

    ``taker_user_id`` mantém o tomador principal (quem criou a reserva) para
    compatibilidade com o schema original. Os tomadores efetivos de cada cota
    ficam em :class:`FiscalDocumentTaker`; o CPF nunca é copiado em claro.
    """

    __tablename__ = "fiscal_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_manual', 'issued', 'failed', 'not_required')",
            name="status_valid",
        ),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        UniqueConstraint("booking_id", name="uq_fiscal_documents_booking"),
        Index("ix_fiscal_documents_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    issuer_cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    taker_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_manual", server_default="pending_manual"
    )
    number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class FiscalDocumentTaker(Base):
    """Tomador e cota da nota, um por jogador da reserva (ADR 0049 §3.6).

    O CPF é um snapshot cifrado do perfil no instante da emissão. A AAD é o
    ``user_id``: o valor não decifra se for copiado para outro tomador.
    """

    __tablename__ = "fiscal_document_takers"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        UniqueConstraint(
            "fiscal_document_id",
            "user_id",
            name="uq_fiscal_document_takers_document_user",
        ),
        Index("ix_fiscal_document_takers_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fiscal_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fiscal_documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cpf_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cpf_key_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
