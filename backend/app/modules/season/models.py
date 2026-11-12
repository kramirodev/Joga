"""Modelos de temporada, XP e streak (ADR 0043, Fase 14D.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
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

SEASON_STATUSES = ("draft", "active", "closed")
XP_SOURCES = ("match", "win", "mission", "new_venue", "admin")


class Season(Base):
    """Temporada de três meses. Uma por trimestre."""

    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'closed')", name="status_valid"),
        CheckConstraint("ends_at > starts_at", name="time_order_valid"),
        CheckConstraint("track_version > 0", name="track_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active", server_default=text("'active'")
    )
    track_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class XpEvent(Base):
    """Evento de XP. Append-only, com chave de idempotência."""

    __tablename__ = "xp_events"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "source IN ('match','win','mission','new_venue','admin')", name="source_valid"
        ),
        Index("ix_xp_events_user_season", "user_id", "season_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class SeasonProgress(Base):
    """Projeção de XP e nível por temporada. Reconstruível a partir do ledger."""

    __tablename__ = "season_progress"
    __table_args__ = (
        CheckConstraint("xp_total >= 0", name="xp_non_negative"),
        CheckConstraint("level >= 0", name="level_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True
    )
    xp_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class WinStreak(Base):
    """Vitórias consecutivas com validade semanal (ADR 0043 §4)."""

    __tablename__ = "win_streaks"
    __table_args__ = (
        CheckConstraint("current_wins >= 0", name="current_non_negative"),
        CheckConstraint("best_wins >= 0", name="best_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_wins: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    best_wins: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_match_week: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_match_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class SeasonItem(Base):
    """Item cosmético de temporada. Substitui o catálogo completo no piloto."""

    __tablename__ = "season_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('accessory','emote','lobby_animation','entry_icon','badge')",
            name="category_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    artwork_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class SeasonTrackLevel(Base):
    """Degrau da trilha: XP exigido, item e ingressos grátis."""

    __tablename__ = "season_track_levels"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 30", name="level_valid"),
        CheckConstraint("xp_required >= 0", name="xp_non_negative"),
        CheckConstraint("free_tickets >= 0", name="tickets_non_negative"),
        CheckConstraint("track IN ('free', 'pass')", name="track_valid"),
    )

    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    xp_required: Mapped[int] = mapped_column(Integer, nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    free_tickets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    track: Mapped[str] = mapped_column(
        String(6), nullable=False, default="free", server_default=text("'free'")
    )


class SeasonClaim(Base):
    """Recompensa de nível reivindicada. Impede resgate duplicado."""

    __tablename__ = "season_claims"
    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 30", name="level_valid"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class Badge(Base):
    """Insígnia ou medalha exibida no perfil.

    `kind` separa os dois conceitos: insígnia é de temporada ou fundador;
    medalha é conquista competitiva e não se confunde com insígnia.
    """

    __tablename__ = "badges"
    __table_args__ = (
        CheckConstraint("kind IN ('season', 'founder', 'medal')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True
    )
    artwork_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PlayerBadge(Base):
    """Insígnia conquistada. Até três equipadas no perfil."""

    __tablename__ = "player_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_player_badges_user_badge"),
        CheckConstraint(
            "equipped_slot IS NULL OR equipped_slot BETWEEN 1 AND 3",
            name="slot_valid",
        ),
        Index(
            "uq_player_badges_user_slot",
            "user_id",
            "equipped_slot",
            unique=True,
            postgresql_where=text("equipped_slot IS NOT NULL"),
            sqlite_where=text("equipped_slot IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("badges.id", ondelete="CASCADE"), nullable=False
    )
    equipped_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PlayerItem(Base):
    """Item cosmético conquistado. Placeholder até o catálogo completo."""

    __tablename__ = "player_items"
    __table_args__ = (UniqueConstraint("user_id", "item_code", name="uq_player_items"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_code: Mapped[str] = mapped_column(String(40), nullable=False)
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class MissionProgress(Base):
    """Progresso semanal de missão. O reset é uma linha nova por semana."""

    __tablename__ = "mission_progress"
    __table_args__ = (
        CheckConstraint("progress >= 0", name="progress_non_negative"),
        Index("ix_mission_progress_user_week", "user_id", "week_start"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True
    )
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    mission_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
