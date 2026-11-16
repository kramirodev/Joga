"""Assinatura do passe e entregas mensais (ADR 0042 §2, ADR 0043 §2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
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

PASS_STATUSES = ("pending", "active", "expired", "cancelled")


class PassSubscription(Base):
    """Trimestre pago pelo jogador. A entrega é mensal e não acumula."""

    __tablename__ = "pass_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("tickets_per_month > 0", name="tickets_positive"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        Index("ix_pass_subscriptions_user_created", "user_id", "created_at"),
        Index("ix_pass_subscriptions_status_ends", "status", "ends_at"),
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
    plan_code: Mapped[str] = mapped_column(String(20), nullable=False)
    tickets_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pending", server_default=text("'pending'")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class PassDelivery(Base):
    """Franquia de um mês. Uma linha por (assinatura, mês), sem retroação."""

    __tablename__ = "pass_deliveries"
    __table_args__ = (
        CheckConstraint("month_index BETWEEN 1 AND 3", name="month_index_valid"),
        CheckConstraint("tickets > 0", name="tickets_positive"),
        UniqueConstraint(
            "subscription_id",
            "month_index",
            name="uq_pass_deliveries_subscription_month",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pass_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    month_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
