"""Modelos de reservas, bloqueios e temporizadores (Fase 13A)."""

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
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

BOOKING_STATUSES = (
    "PARTICIPANT_CONFIRMATION",
    "REQUESTED",
    "DECLINED",
    "EXPIRED",
    "HOLD_CONFIRMED",
    "PAYMENT_PENDING",
    "CONFIRMED",
    "CANCELLED",
    "CANCELLED_BY_VENUE",
    "CANCELLED_BY_PLAYER",
    "SUBSTITUTING",
    "COMPLETED",
)
TERMINAL_BOOKING_STATUSES = frozenset(
    {
        "DECLINED",
        "EXPIRED",
        "CANCELLED",
        "CANCELLED_BY_VENUE",
        "CANCELLED_BY_PLAYER",
        "COMPLETED",
    }
)
PAYMENT_STATUSES = ("PENDING", "PAID", "REFUNDED", "FAILED", "WAIVED")
HOLD_STATUSES = ("ACTIVE", "RELEASED", "EXPIRED")
TIMER_TYPES = ("T1", "T2", "T3")
TIMER_STATUSES = ("RUNNING", "COMPLETED", "EXPIRED", "CANCELLED")
SUBSTITUTION_STATUSES = ("OPEN", "CALLED", "AWAITING_PAYMENT", "FILLED", "EXPIRED", "CANCELLED")
PRESENCE_STATUSES = ("PENDING", "PRESENT", "UNVERIFIED", "NO_SHOW")


class Booking(Base):
    """Solicitação de reserva de um lobby para um espaço e intervalo."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'PARTICIPANT_CONFIRMATION', 'REQUESTED', 'DECLINED', 'EXPIRED', "
            "'HOLD_CONFIRMED', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED', "
            "'CANCELLED_BY_VENUE', 'CANCELLED_BY_PLAYER', 'SUBSTITUTING', 'COMPLETED'"
            ")",
            name="status_valid",
        ),
        CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        CheckConstraint("price_cents >= 0", name="price_non_negative"),
        CheckConstraint("seats > 0", name="seats_positive"),
        CheckConstraint("payment_version > 0", name="payment_version_positive"),
        UniqueConstraint("lobby_id", name="uq_bookings_lobby"),
        Index("ix_bookings_organization_status", "organization_id", "status"),
        Index("ix_bookings_space_start", "venue_space_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    organization_venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_venues.id", ondelete="RESTRICT"), nullable=False
    )
    venue_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PARTICIPANT_CONFIRMATION",
        server_default=text("'PARTICIPANT_CONFIRMATION'"),
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="BRL", server_default=text("'BRL'")
    )
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    cancellation_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    payment_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hold_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    presence_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    players_per_team: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    formation_note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
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


class BookingParticipant(Base):
    """Vaga de participante em uma reserva, com contribuição e pagamento."""

    __tablename__ = "booking_participants"
    __table_args__ = (
        CheckConstraint("seat > 0", name="seat_positive"),
        CheckConstraint("contribution_cents >= 0", name="contribution_non_negative"),
        CheckConstraint(
            "payment_status IN ('PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED')",
            name="payment_status_valid",
        ),
        CheckConstraint(
            "settled_with IS NULL OR settled_with IN ('pix', 'tickets')",
            name="settled_with_valid",
        ),
        CheckConstraint("tickets_consumed >= 0", name="tickets_consumed_non_negative"),
        Index(
            "uq_booking_participants_active_seat",
            "booking_id",
            "seat",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
        Index(
            "uq_booking_participants_active_user",
            "booking_id",
            "user_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
        Index("ix_booking_participants_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    seat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    contribution_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default=text("'PENDING'")
    )
    settled_with: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tickets_consumed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pre_checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    presence_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default=text("'PENDING'")
    )
    presence_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    presence_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    presence_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    presence_accuracy_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
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


class BookingHold(Base):
    """Bloqueio temporário de um espaço por uma reserva."""

    __tablename__ = "booking_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'EXPIRED')",
            name="status_valid",
        ),
        CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        Index("ix_booking_holds_space_status_start", "venue_space_id", "status", "starts_at"),
        Index("ix_booking_holds_booking", "booking_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    venue_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venue_spaces.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'")
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    release_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BookingTimer(Base):
    """Temporizador independente de reserva (T1, T2 ou T3)."""

    __tablename__ = "booking_timers"
    __table_args__ = (
        CheckConstraint("timer_type IN ('T1', 'T2', 'T3')", name="timer_type_valid"),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'EXPIRED', 'CANCELLED')",
            name="status_valid",
        ),
        UniqueConstraint("booking_id", "timer_type", name="uq_booking_timers_booking_type"),
        Index("ix_booking_timers_status_deadline", "status", "deadline_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    timer_type: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="RUNNING", server_default=text("'RUNNING'")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class BookingEvent(Base):
    """Histórico append-only de transições e ações da reserva."""

    __tablename__ = "booking_events"
    __table_args__ = (Index("ix_booking_events_booking_created", "booking_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class BookingPayment(Base):
    """Cobrança simulada por participante; o PSP real entra na Fase 14."""

    __tablename__ = "booking_payments"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        CheckConstraint(
            "status IN ('PENDING', 'PAID', 'REFUNDED', 'FAILED', 'WAIVED', 'EXPIRED')",
            name="status_valid",
        ),
        UniqueConstraint(
            "booking_id",
            "participant_id",
            "version",
            name="uq_booking_payments_participant_version",
        ),
        UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_booking_payments_provider_order",
        ),
        UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_booking_payments_provider_payment",
        ),
        Index("ix_booking_payments_booking_status", "booking_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_participants.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default=text("'PENDING'")
    )
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
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


class BookingSubstitution(Base):
    """Vaga aberta após desistência, com prazo T4 para substituição (ADR 0039)."""

    __tablename__ = "booking_substitutions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'CALLED', 'AWAITING_PAYMENT', 'FILLED', 'EXPIRED', 'CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint("seat > 0", name="seat_positive"),
        Index("ix_booking_substitutions_booking_status", "booking_id", "status"),
        Index("ix_booking_substitutions_deadline", "status", "deadline_at"),
        Index(
            "uq_booking_substitutions_open_seat",
            "booking_id",
            "seat",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    seat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    outgoing_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    filled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    substitute_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="SET NULL"), nullable=True
    )
    covered_by_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_payments.id", ondelete="SET NULL"), nullable=True
    )
    called_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    call_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    call_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    paid_seat: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", server_default=text("'OPEN'")
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
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


class BookingRefundExclusion(Base):
    """Participante que não deve ser reembolsado em cancelamento (ADR 0039)."""

    __tablename__ = "booking_refund_exclusions"
    __table_args__ = (
        UniqueConstraint("booking_id", "user_id", name="uq_booking_refund_exclusions_user"),
        Index("ix_booking_refund_exclusions_booking", "booking_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
