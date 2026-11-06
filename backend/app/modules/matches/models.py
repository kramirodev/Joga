"""Modelos do ciclo de vida da partida."""

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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

MATCH_STATES = (
    "PENDING_CONFIRMATION",
    "READY",
    "IN_PROGRESS",
    "RESULT_PENDING",
    "FINALIZED",
    "DISPUTED",
    "VOIDED",
    "CANCELLED",
    "EXPIRED",
)

PARTICIPANT_STATUSES = ("invited", "confirmed", "declined", "checked_in", "no_show")


class Match(Base):
    """Partida vinculada a um lobby, com estado controlado no servidor."""

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING_CONFIRMATION', 'READY', 'IN_PROGRESS', 'RESULT_PENDING', "
            "'FINALIZED', 'DISPUTED', 'VOIDED', 'CANCELLED', 'EXPIRED')",
            name="state_valid",
        ),
        CheckConstraint("scheduled_end_at > scheduled_start_at", name="time_order_valid"),
        CheckConstraint(
            "confirmation_deadline <= scheduled_start_at", name="confirmation_before_start"
        ),
        CheckConstraint("check_in_opens_at <= check_in_deadline", name="checkin_order_valid"),
        CheckConstraint(
            "check_in_deadline <= substitution_deadline", name="substitution_order_valid"
        ),
        CheckConstraint(
            "substitution_deadline <= scheduled_start_at", name="substitution_before_start"
        ),
        CheckConstraint(
            "final_result IS NULL OR final_result IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="final_result_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING_CONFIRMATION")
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmation_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_in_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_in_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    substitution_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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


class MatchParticipant(Base):
    """Participante da partida e seu estado de confirmação/presença."""

    __tablename__ = "match_participants"
    __table_args__ = (
        CheckConstraint("team IN (1, 2)", name="team_valid"),
        CheckConstraint(
            "status IN ('invited', 'confirmed', 'declined', 'checked_in', 'no_show')",
            name="status_valid",
        ),
        CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        UniqueConstraint("match_id", "user_id", name="uq_match_participants_user"),
        Index("ix_match_participants_match_status", "match_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    is_substitute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_captain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    captain_selection_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    captain_selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    queue_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="SET NULL"), nullable=True
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class MatchStateTransition(Base):
    """Trilha append-only das transições de estado."""

    __tablename__ = "match_state_transitions"
    __table_args__ = (
        CheckConstraint("to_state <> ''", name="to_state_not_empty"),
        Index("ix_match_state_transitions_match", "match_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_state: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
