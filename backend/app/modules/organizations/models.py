"""Modelos de organizações, membros e estabelecimentos."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow


class Organization(Base):
    """Entidade comercial proprietária de estabelecimentos e recursos."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'closed')",
            name="status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
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
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="America/Sao_Paulo",
        server_default=text("'America/Sao_Paulo'"),
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
