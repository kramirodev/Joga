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

REFUND_STATUSES = ("PENDING", "PROCESSED", "FAILED")
RELEASE_STATUSES = ("PENDING", "RELEASED", "FAILED", "REVERSED")
DISPUTE_STATUSES = ("OPEN", "ACCEPTED", "REJECTED", "WITHDRAWN")


class PaymentRefund(Base):
    """Reembolso de uma cobrança Pix, total ou parcial (Fase 14E-E).

    O comportamento atual continua criando apenas ``FULL``. O schema aceita
    ``PARTIAL`` sem alterar nenhum fluxo: a unicidade de reembolso integral é
    garantida por índice parcial, e ``idempotency_key`` permite repetir um
    pedido parcial sem duplicar.
    """

    __tablename__ = "payment_refunds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint("refund_type IN ('FULL', 'PARTIAL')", name="refund_type_valid"),
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        Index(
            "uq_payment_refunds_full_payment",
            "booking_payment_id",
            unique=True,
            postgresql_where=text("refund_type = 'FULL'"),
            sqlite_where=text("refund_type = 'FULL'"),
        ),
        Index("ix_payment_refunds_booking_created", "booking_id", "created_at"),
        Index("uq_payment_refunds_idempotency_key", "idempotency_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    booking_payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="FULL", server_default="FULL"
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
        Index("ix_psp_webhook_events_retry", "processed_at", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PurchasePayment(Base):
    """Cobrança Pix de uma compra de pacote ou de passe (Fase 14D.13).

    Não usa ``booking_payments``: o fluxo de ingresso não tem reserva,
    participante nem repasse. A referência é polimórfica por ``kind``.
    """

    __tablename__ = "purchase_payments"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ticket_pack', 'pass')",
            name="kind_valid",
        ),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        UniqueConstraint("kind", "reference_id", name="uq_purchase_payments_reference"),
        UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_purchase_payments_provider_order",
        ),
        UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_purchase_payments_provider_payment",
        ),
        Index("ix_purchase_payments_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_status_detail: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    qr_code_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    # Snapshot da janela de contestação no instante da criação da liberação.
    # Não recalcular quando a configuração mudar.
    dispute_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    # Cópia do prazo da liberação no instante da abertura; não recalcular.
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
