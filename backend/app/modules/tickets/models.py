"""Ledger e saldo de ingressos (ADR 0042 §2, Fase 14D.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

TICKET_SOURCES = (
    "purchase",
    "pass",
    "free_level",
    "consumption",
    "refund",
    "expired",
    "admin",
)

PURCHASE_STATUSES = ("pending", "paid", "cancelled")


class TicketPack(Base):
    """Pacote de ingressos à venda. Preço decrescente por tamanho (ADR 0042 §3)."""

    __tablename__ = "ticket_packs"
    __table_args__ = (
        CheckConstraint("tickets > 0", name="tickets_positive"),
        CheckConstraint("unit_price_cents > 0", name="unit_price_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    @property
    def amount_cents(self) -> int:
        return self.tickets * self.unit_price_cents


class TicketPurchase(Base):
    """Intenção de compra de pacote. A cobrança real entra na Fase 14B."""

    __tablename__ = "ticket_purchases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("tickets > 0", name="tickets_positive"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("ix_ticket_purchases_user_created", "user_id", "created_at"),
        Index(
            "uq_ticket_purchases_pending_pack",
            "user_id",
            "pack_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ticket_packs.id", ondelete="RESTRICT"), nullable=False
    )
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pending", server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketLedgerEntry(Base):
    """Movimento de ingresso. Append-only: correção é evento novo."""

    __tablename__ = "ticket_ledger"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        CheckConstraint(
            "source IN ('purchase','pass','free_level','consumption','refund','expired','admin')",
            name="source_valid",
        ),
        Index("ix_ticket_ledger_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class TicketBalance(Base):
    """Saldo projetado. Reconstruível a partir do ledger."""

    __tablename__ = "ticket_balances"
    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class TicketLot(Base):
    """Lote de ingressos com origem, saldo e validade próprios.

    O saldo de ``ticket_balances`` é a soma dos lotes ativos. Lotes expirados
    permanecem para auditoria, mas não contam no saldo.
    """

    __tablename__ = "ticket_lots"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="original_amount_positive"),
        CheckConstraint(
            "remaining >= 0 AND remaining <= original_amount",
            name="remaining_valid",
        ),
        CheckConstraint(
            "source IN ('purchase','pass','free_level','admin','refund')",
            name="source_valid",
        ),
        Index("ix_ticket_lots_user_expiry", "user_id", "expires_at"),
        Index("ix_ticket_lots_user_source", "user_id", "source"),
        Index("ix_ticket_lots_user_period", "user_id", "period"),
        CheckConstraint(
            "source <> 'pass' OR period IS NOT NULL",
            name="pass_period_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    original_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    # Franquia do passe: 'YYYY-MM'. Não é validade de crédito comprado.
    period: Mapped[str | None] = mapped_column(String(7), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_ledger.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class TicketLotConsumption(Base):
    """Relação entre consumo de uma reserva e o lote de origem."""

    __tablename__ = "ticket_lot_consumptions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("lot_id", "ref_type", "ref_id", name="uq_ticket_lot_consumption_ref"),
        Index("ix_ticket_lot_consumptions_user_ref", "user_id", "ref_type", "ref_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ticket_lots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_ledger.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
