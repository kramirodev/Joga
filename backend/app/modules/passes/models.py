"""Catálogo, assinatura e ciclos mensais do passe (ADR 0070).

O contrato é de 1, 3 ou 6 meses. A franquia continua sendo entregue mês a mês,
a partir da data da compra (mês de aniversário), e não acumula. ``ticket_lots``
segue sendo a fonte da verdade do saldo; o ciclo registra a janela de validade.
"""

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
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

PASS_STATUSES = (
    "pending",
    "scheduled",
    "active",
    "expired",
    "cancelled",
    "refunded",
    "payment_failed",
)
PASS_DELIVERY_STATUSES = ("scheduled", "delivered", "closed", "cancelled")
PASS_MONTH_OPTIONS = (1, 3, 6)


class PassPlan(Base):
    """Plano do catálogo: tamanho da franquia × duração do contrato."""

    __tablename__ = "pass_plans"
    __table_args__ = (
        CheckConstraint("months IN (1, 3, 6)", name="months_valid"),
        CheckConstraint("tickets_per_month > 0", name="tickets_positive"),
        CheckConstraint(
            "unit_price_cents BETWEEN 300 AND 370",
            name="unit_price_range",
        ),
        CheckConstraint(
            "cycle_amount_cents = tickets_per_month * months * unit_price_cents",
            name="cycle_amount_matches",
        ),
        CheckConstraint("installments = 1", name="installments_valid"),
        CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        UniqueConstraint("code", name="uq_pass_plans_code"),
        Index("ix_pass_plans_active_size", "active", "months", "tickets_per_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    months: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tickets_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Pix do Mercado Pago é à vista nesta fase; parcelamento do semestral é
    # decisão de produto/PSP pendente (ADR 0070 §3.3).
    installments: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default=text("1")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    catalog_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    @property
    def monthly_cents(self) -> int:
        return self.tickets_per_month * self.unit_price_cents


class PassSubscription(Base):
    """Contrato pago pelo jogador. A entrega é mensal e não acumula."""

    __tablename__ = "pass_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'scheduled', 'active', 'expired', "
            "'cancelled', 'refunded', 'payment_failed')",
            name="status_valid",
        ),
        CheckConstraint("tickets_per_month > 0", name="tickets_positive"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("cycle_months IN (1, 3, 6)", name="cycle_months_valid"),
        CheckConstraint(
            "unit_price_cents BETWEEN 300 AND 370",
            name="unit_price_range",
        ),
        CheckConstraint("installments = 1", name="installments_valid"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        Index("ix_pass_subscriptions_user_created", "user_id", "created_at"),
        Index("ix_pass_subscriptions_status_ends", "status", "ends_at"),
        Index("ix_pass_subscriptions_user_status", "user_id", "status"),
        Index(
            "uq_pass_subscriptions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(24), nullable=False)
    tickets_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_months: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3, server_default=text("3")
    )
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    installments: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default=text("1")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pass_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_window_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class PassDelivery(Base):
    """Ciclo mensal da franquia, com janela de aniversário explícita."""

    __tablename__ = "pass_deliveries"
    __table_args__ = (
        CheckConstraint("month_index BETWEEN 1 AND 6", name="month_index_valid"),
        CheckConstraint("tickets > 0", name="tickets_positive"),
        CheckConstraint(
            "status IN ('scheduled', 'delivered', 'closed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        UniqueConstraint(
            "subscription_id",
            "month_index",
            name="uq_pass_deliveries_subscription_month",
        ),
        UniqueConstraint(
            "subscription_id",
            "period",
            name="uq_pass_deliveries_subscription_period",
        ),
        Index("ix_pass_deliveries_status_ends", "status", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pass_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    month_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    # Rótulo de competência do ciclo (`YYYY-MM`), derivado do seu início.
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="scheduled", server_default=text("'scheduled'")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
