"""Modelos de quadras, modalidades, agenda, bloqueios e fotos (Fase 12A)."""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

PHOTO_STATUSES = ("PENDING", "APPROVED", "REJECTED", "REMOVED")


class VenueSpace(Base):
    """Quadra ou espaço reservável de um estabelecimento."""

    __tablename__ = "venue_spaces"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="status_valid"),
        UniqueConstraint(
            "organization_venue_id",
            "name",
            name="uq_venue_spaces_venue_name",
        ),
        Index("ix_venue_spaces_organization_venue_id", "organization_venue_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_venues.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(280), nullable=True)
    is_covered: Mapped[bool] = mapped_column(
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


class VenueSport(Base):
    """Vínculo entre uma quadra/espaço e uma modalidade do catálogo."""

    __tablename__ = "venue_sports"
    __table_args__ = (
        UniqueConstraint("venue_space_id", "sport_id", name="uq_venue_sports_space_sport"),
        Index("ix_venue_sports_sport_id", "sport_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="CASCADE"), nullable=False
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class VenueAvailability(Base):
    """Janela semanal recorrente de funcionamento e preço de uma quadra."""

    __tablename__ = "venue_availability"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_valid"),
        CheckConstraint("start_time < end_time", name="time_order_valid"),
        CheckConstraint("price_cents >= 0", name="price_non_negative"),
        CheckConstraint("slot_minutes BETWEEN 15 AND 240", name="slot_minutes_valid"),
        UniqueConstraint(
            "venue_space_id",
            "weekday",
            "start_time",
            name="uq_venue_availability_space_weekday_start",
        ),
        Index("ix_venue_availability_space_weekday", "venue_space_id", "weekday"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    band_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pricing_bands.id", ondelete="RESTRICT"), nullable=True
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


class VenueBlackout(Base):
    """Bloqueio manual ou reserva externa que retira um horário da agenda."""

    __tablename__ = "venue_blackouts"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        Index("ix_venue_blackouts_space_start", "venue_space_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class VenuePhoto(Base):
    """Foto de quadra/estabelecimento, com revisão e remoção auditáveis."""

    __tablename__ = "venue_photos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'REMOVED')",
            name="status_valid",
        ),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
        CheckConstraint(
            "(status <> 'REJECTED') OR (rejection_reason IS NOT NULL)",
            name="rejection_reason_required",
        ),
        Index("ix_venue_photos_venue_status", "organization_venue_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_venues.id", ondelete="CASCADE"), nullable=False
    )
    venue_space_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default=text("'PENDING'")
    )
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
