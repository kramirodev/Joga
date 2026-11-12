"""Modelos de eventos de PSP e ledger financeiro interno (Fase 14A)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

LEDGER_ENTRY_TYPES = ("CHARGE_CREATED", "PAYMENT_CONFIRMED", "PAYMENT_REFUNDED", "VENUE_RELEASE")
REFUND_STATUSES = ("PENDING", "PROCESSED", "FAILED")
RELEASE_STATUSES = ("PENDING", "RELEASED", "FAILED", "REVERSED")
DISPUTE_STATUSES = ("OPEN", "ACCEPTED", "REJECTED", "WITHDRAWN")


class PaymentRefund(Base):
    """Reembolso idempotente de uma cobrança Pix."""

    __tablename__ = "payment_refunds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        UniqueConstraint("booking_payment_id", name="uq_payment_refunds_payment"),
        Index("ix_payment_refunds_booking_created", "booking_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    booking_payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PaymentEvent(Base):
    """Evento append-only de uma cobrança, vindo do PSP ou do simulador."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event"),
        Index("ix_payment_events_payment_created", "booking_payment_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PspWebhookEvent(Base):
    """Webhook bruto do PSP, usado para idempotência e auditoria."""

    __tablename__ = "psp_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_psp_webhook_events_provider_event",
        ),
        Index("ix_psp_webhook_events_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class LedgerEntry(Base):
    """Registro append-only de direitos e obrigações financeiras internas."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ("
            "'CHARGE_CREATED', 'PAYMENT_CONFIRMED', 'PAYMENT_REFUNDED', 'VENUE_RELEASE'"
            ")",
            name="entry_type_valid",
        ),
        CheckConstraint("direction IN ('DEBIT', 'CREDIT')", name="direction_valid"),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        Index("ix_ledger_entries_booking_created", "booking_id", "created_at"),
        UniqueConstraint(
            "booking_payment_id",
            "entry_type",
            name="uq_ledger_entries_payment_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    booking_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="SET NULL"), nullable=True
    )
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="POSTED", server_default="POSTED"
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class VenueRelease(Base):
    """Valor devido ao estabelecimento por uma reserva concluída (Fase 15)."""

    __tablename__ = "venue_releases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RELEASED', 'FAILED', 'REVERSED')",
            name="status_valid",
        ),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        UniqueConstraint("booking_id", name="uq_venue_releases_booking"),
        Index("ix_venue_releases_org_status_eligible", "organization_id", "status", "eligible_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
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


class FinancialDispute(Base):
    """Contestação do estabelecimento sobre valores de uma reserva (Fase 15)."""

    __tablename__ = "financial_disputes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'ACCEPTED', 'REJECTED', 'WITHDRAWN')",
            name="status_valid",
        ),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        Index(
            "ix_financial_disputes_org_status_created", "organization_id", "status", "created_at"
        ),
        Index(
            "uq_financial_disputes_open_booking",
            "booking_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venue_releases.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", server_default="OPEN"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
