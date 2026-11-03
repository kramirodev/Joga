"""Modelos de fila, lobby e execuções de matchmaking."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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

MODES = ("casual", "ranked")
QUEUE_STATUSES = ("waiting", "matched", "cancelled", "expired")
LOBBY_ORIGINS = ("matchmaking", "manual")
LOBBY_STATUSES = ("scheduled", "cancelled", "completed")
RUN_STATUSES = ("running", "completed", "failed")


class QueueEntry(Base):
    """Entrada persistente na fila de matchmaking."""

    __tablename__ = "queue_entries"
    __table_args__ = (
        CheckConstraint("mode IN ('casual', 'ranked')", name="mode_valid"),
        CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        CheckConstraint(
            "status IN ('waiting', 'matched', 'cancelled', 'expired')",
            name="status_valid",
        ),
        CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
        Index(
            "uq_queue_entries_active",
            "user_id",
            "format_id",
            "mode",
            unique=True,
            postgresql_where=text("status = 'waiting'"),
            sqlite_where=text("status = 'waiting'"),
        ),
        Index("ix_queue_entries_waiting", "format_id", "mode", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="casual")
    court_preference: Mapped[str] = mapped_column(String(20), nullable=False, default="ANY")
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[int] = mapped_column(Integer, nullable=False)
    lobby_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lobbies.id", ondelete="SET NULL"), nullable=True, index=True
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
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Lobby(Base):
    """Agrupamento formado pelo matchmaking, com horário concreto."""

    __tablename__ = "lobbies"
    __table_args__ = (
        CheckConstraint("origin IN ('matchmaking', 'manual')", name="origin_valid"),
        CheckConstraint("mode IN ('casual', 'ranked')", name="mode_valid"),
        CheckConstraint("status IN ('scheduled', 'cancelled', 'completed')", name="status_valid"),
        CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        CheckConstraint("scheduled_end_at > scheduled_start_at", name="time_order_valid"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="matchmaking")
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="casual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    court_preference: Mapped[str] = mapped_column(String(20), nullable=False, default="ANY")
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[int] = mapped_column(Integer, nullable=False)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL"), nullable=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class LobbyParticipant(Base):
    """Participante de um lobby, com equipe e nível no momento da formação."""

    __tablename__ = "lobby_participants"
    __table_args__ = (
        CheckConstraint("team IN (1, 2)", name="team_valid"),
        CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
        UniqueConstraint("lobby_id", "user_id", name="uq_lobby_participants_user"),
        UniqueConstraint("queue_entry_id", name="uq_lobby_participants_entry"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    queue_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class MatchmakingRun(Base):
    """Registro auditável de cada rodada do worker."""

    __tablename__ = "matchmaking_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="status_valid"),
        CheckConstraint("entries_expired >= 0", name="expired_non_negative"),
        CheckConstraint("lobbies_formed >= 0", name="lobbies_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    entries_expired: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lobbies_formed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
