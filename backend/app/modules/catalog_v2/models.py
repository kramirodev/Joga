"""Modelos do catálogo v2 (ADR 0079).

Tabelas aditivas ao piloto da ADR 0070. Nada aqui substitui ``pass_plans``,
``pass_subscriptions`` ou ``pass_deliveries``: o catálogo antigo permanece
intacto e o legado não expira.

- ``catalog_v2_products``: três planos mensais de tickets e um passe de
  temporada, com entitlements distintos.
- ``catalog_v2_prices``: preço de tabela por meio e parcelamento, versionado.
- ``catalog_v2_subscriptions`` / ``catalog_v2_subscription_cycles``: assinatura
  mensal e suas entregas.
- ``catalog_v2_season_passes`` / ``catalog_v2_season_pass_deliveries``: passe
  cobrado uma vez e a entrega dos tickets inclusos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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

CATALOG_V2_VERSION = 2

PRODUCT_KINDS = ("subscription", "season_pass")
PAYMENT_METHODS = ("pix", "card")
INSTALLMENT_OPTIONS = (1, 3)
ENTITLEMENT_KEYS = (
    "tickets",
    "season_track",
    "cosmetics",
    "advanced_stats",
    "private_lobby",
    "cep_search",
)
SUBSCRIPTION_STATUSES = (
    "pending",
    "active",
    "past_due",
    "cancelled",
    "expired",
    "refunded",
)
SEASON_PASS_STATUSES = ("pending", "active", "expired", "cancelled", "refunded")
DELIVERY_STATUSES = ("scheduled", "delivered", "closed", "cancelled")


class CatalogV2Product(Base):
    """Plano mensal de tickets ou passe de temporada."""

    __tablename__ = "catalog_v2_products"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('subscription', 'season_pass')",
            name="kind_valid",
        ),
        CheckConstraint("months IN (1, 3)", name="months_valid"),
        CheckConstraint(
            "kind <> 'subscription' OR (months = 1 AND tickets_per_month > 0)",
            name="subscription_valid",
        ),
        CheckConstraint(
            "kind <> 'season_pass' OR (months = 3 AND tickets_included >= 0)",
            name="season_pass_valid",
        ),
        CheckConstraint(
            "catalog_version > 0",
            name="catalog_version_positive",
        ),
        UniqueConstraint("code", name="uq_catalog_v2_products_code"),
        Index("ix_catalog_v2_products_active_kind", "active", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    months: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tickets_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tickets_included: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=CATALOG_V2_VERSION, server_default=text("2")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    @property
    def is_subscription(self) -> bool:
        return self.kind == "subscription"

    @property
    def is_season_pass(self) -> bool:
        return self.kind == "season_pass"


class CatalogV2ProductEntitlement(Base):
    """Entitlement habilitado por produto. Assinatura não libera o passe."""

    __tablename__ = "catalog_v2_product_entitlements"
    __table_args__ = (
        CheckConstraint(
            "entitlement_key IN ('tickets', 'season_track', 'cosmetics', "
            "'advanced_stats', 'private_lobby', 'cep_search')",
            name="entitlement_key_valid",
        ),
        UniqueConstraint(
            "product_id",
            "entitlement_key",
            name="uq_catalog_v2_product_entitlements_product_key",
        ),
        Index(
            "ix_catalog_v2_product_entitlements_product",
            "product_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_products.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_key: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class CatalogV2Price(Base):
    """Preço de tabela congelado por versão, meio e parcelamento.

    O cliente nunca envia preço. Mudança de taxa exige nova ``catalog_version``;
    o histórico não é editado.
    """

    __tablename__ = "catalog_v2_prices"
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        CheckConstraint("installments IN (1, 3)", name="installments_valid"),
        CheckConstraint(
            "payment_method <> 'pix' OR installments = 1",
            name="pix_single_installment",
        ),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        UniqueConstraint(
            "product_id",
            "payment_method",
            "installments",
            "catalog_version",
            name="uq_catalog_v2_prices_version",
        ),
        Index(
            "ix_catalog_v2_prices_product_method",
            "product_id",
            "payment_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_products.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(8), nullable=False)
    installments: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class CatalogV2Subscription(Base):
    """Assinatura mensal de tickets. Cartão somente 1x; Pix à vista."""

    __tablename__ = "catalog_v2_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'past_due', 'cancelled', 'expired', 'refunded')",
            name="status_valid",
        ),
        CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        CheckConstraint("installments = 1", name="subscription_single_installment"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        Index(
            "uq_catalog_v2_subscriptions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_catalog_v2_subscriptions_user_created", "user_id", "created_at"),
        Index("ix_catalog_v2_subscriptions_status_ends", "status", "ends_at"),
        Index("ix_catalog_v2_subscriptions_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_products.id", ondelete="RESTRICT"), nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False)
    tickets_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(8), nullable=False)
    installments: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default=text("1")
    )
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class CatalogV2SubscriptionCycle(Base):
    """Entrega mensal da franquia. Não acumula e expira no fim do ciclo."""

    __tablename__ = "catalog_v2_subscription_cycles"
    __table_args__ = (
        CheckConstraint("month_index BETWEEN 1 AND 3", name="month_index_valid"),
        CheckConstraint("tickets > 0", name="tickets_positive"),
        CheckConstraint(
            "status IN ('scheduled', 'delivered', 'closed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        UniqueConstraint(
            "subscription_id",
            "month_index",
            name="uq_catalog_v2_subscription_cycles_month",
        ),
        UniqueConstraint(
            "subscription_id",
            "period",
            name="uq_catalog_v2_subscription_cycles_period",
        ),
        Index("ix_catalog_v2_subscription_cycles_status_ends", "status", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    month_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="scheduled", server_default=text("'scheduled'")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class CatalogV2SeasonPass(Base):
    """Passe de temporada: cobrança única, benefícios distintos da assinatura."""

    __tablename__ = "catalog_v2_season_passes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'cancelled', 'refunded')",
            name="status_valid",
        ),
        CheckConstraint(
            "payment_method IN ('pix', 'card')",
            name="payment_method_valid",
        ),
        CheckConstraint("installments IN (1, 3)", name="installments_valid"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("catalog_version > 0", name="catalog_version_positive"),
        CheckConstraint("tickets_granted >= 0", name="tickets_granted_non_negative"),
        CheckConstraint(
            "tickets_redeemed >= 0 AND tickets_redeemed <= tickets_granted",
            name="tickets_redeemed_valid",
        ),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="time_order_valid",
        ),
        Index(
            "uq_catalog_v2_season_passes_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_catalog_v2_season_passes_user_created", "user_id", "created_at"),
        Index("ix_catalog_v2_season_passes_status_ends", "status", "ends_at"),
        Index("ix_catalog_v2_season_passes_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_products.id", ondelete="RESTRICT"), nullable=False
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(8), nullable=False)
    installments: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default=text("1")
    )
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    tickets_granted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    tickets_redeemed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class CatalogV2SeasonPassDelivery(Base):
    """Entrega única dos tickets inclusos no passe, com expiração de temporada."""

    __tablename__ = "catalog_v2_season_pass_deliveries"
    __table_args__ = (
        CheckConstraint("tickets > 0", name="tickets_positive"),
        CheckConstraint(
            "status IN ('scheduled', 'delivered', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("expires_at > granted_at", name="time_order_valid"),
        UniqueConstraint(
            "season_pass_id",
            name="uq_catalog_v2_season_pass_deliveries_pass",
        ),
        Index("ix_catalog_v2_season_pass_deliveries_status_expires", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    season_pass_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_v2_season_passes.id", ondelete="CASCADE"), nullable=False
    )
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="scheduled", server_default=text("'scheduled'")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
