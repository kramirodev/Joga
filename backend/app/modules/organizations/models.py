"""Modelos de organizações, membros e estabelecimentos."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

JsonType = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class Organization(Base):
    """Entidade comercial proprietária de estabelecimentos e recursos."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'closed')",
            name="status_valid",
        ),
        CheckConstraint(
            "payout_status IN ('pending', 'active', 'blocked')",
            name="payout_status_valid",
        ),
        CheckConstraint(
            "(pix_key IS NULL AND pix_key_type IS NULL) "
            "OR (pix_key IS NOT NULL AND pix_key_type IS NOT NULL)",
            name="pix_key_pair_valid",
        ),
        CheckConstraint(
            "verification_status IN ('pending', 'verified', 'invalid')",
            name="verification_status_valid",
        ),
        Index("uq_organizations_cnpj", "cnpj", unique=True),
        Index("ix_organizations_cnpj_next_check_at", "cnpj_next_check_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    is_platform: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
    )
    # Verificação automática de CNPJ (ADR 0062). O snapshot guarda apenas a
    # resposta mascarada necessária à auditoria e à conferência de endereço.
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    cnpj_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cnpj_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cnpj_next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cnpj_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    legal_document: Mapped[str | None] = mapped_column(String(14), nullable=True)
    pix_key_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pix_key: Mapped[str | None] = mapped_column(String(77), nullable=True)
    payout_status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pending", server_default=text("'pending'")
    )
    payout_verified_at: Mapped[datetime | None] = mapped_column(
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


class OrganizationMembership(Base):
    """Vínculo entre usuário e organização, com papel explícito."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_organization_user",
        ),
        CheckConstraint(
            "role IN ('OWNER', 'ADMIN', 'OPERATOR')",
            name="role_valid",
        ),
        Index("ix_organization_memberships_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
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


class OrganizationVenue(Base):
    """Perfil comercial do estabelecimento vinculado à organização.

    Não confundir com o catálogo `venues` de locais descobertos da Fase 4.
    Quadras, agenda, preços e reservas pertencem à Fase 12.
    """

    __tablename__ = "organization_venues"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="status_valid",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="latitude_valid",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="longitude_valid",
        ),
        CheckConstraint(
            "geocoding_precision IS NULL OR geocoding_precision IN "
            "('street', 'venue', 'approximate', 'manual')",
            name="geocoding_precision_valid",
        ),
        Index("ix_organization_venues_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    geocoding_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geocoding_precision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="America/Sao_Paulo",
        server_default=text("'America/Sao_Paulo'"),
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
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
