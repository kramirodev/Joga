"""Modelos de perfil esportivo, disponibilidade, região e locais."""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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

LEVELS = ("beginner", "intermediate", "advanced")
COURT_PREFERENCES = ("PUBLIC_ONLY", "PRIVATE_ONLY", "ANY")
REGION_SOURCES = ("gps", "cep")
VENUE_KINDS = ("public", "private")


class Sport(Base):
    """Modalidade esportiva do catálogo."""

    __tablename__ = "sports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class SportFormat(Base):
    """Configuração versionada de um formato (duração, equipes e participantes)."""

    __tablename__ = "sport_formats"
    __table_args__ = (
        CheckConstraint("team_size > 0", name="team_size_positive"),
        CheckConstraint(
            "total_participants = team_size * 2",
            name="participants_match_teams",
        ),
        CheckConstraint("play_minutes > 0", name="play_minutes_positive"),
        CheckConstraint("break_minutes >= 0", name="break_minutes_non_negative"),
        CheckConstraint(
            "duration_minutes = play_minutes + break_minutes",
            name="duration_matches_parts",
        ),
        UniqueConstraint("slug", "version", name="uq_sport_formats_slug_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    team_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    play_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class UserProfile(Base):
    """Dados básicos do perfil do jogador."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
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


class UserSportProfile(Base):
    """Nível e preferência de quadra por formato esportivo."""

    __tablename__ = "user_sport_profiles"
    __table_args__ = (
        CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="level_valid",
        ),
        CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        UniqueConstraint("user_id", "format_id", name="uq_user_sport_profiles_user_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    court_preference: Mapped[str] = mapped_column(String(20), nullable=False, default="ANY")
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


class Availability(Base):
    """Janela semanal recorrente de disponibilidade."""

    __tablename__ = "availabilities"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_valid"),
        CheckConstraint("start_time < end_time", name="time_order_valid"),
        UniqueConstraint(
            "user_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_window",
        ),
        Index("ix_availabilities_user_weekday", "user_id", "weekday"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class UserRegion(Base):
    """Centro aproximado de busca; nunca a coordenada residencial exata."""

    __tablename__ = "user_regions"
    __table_args__ = (
        CheckConstraint("source IN ('gps', 'cep')", name="source_valid"),
        CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
        CheckConstraint(
            "source = 'gps' OR (cep IS NOT NULL AND city IS NOT NULL AND state IS NOT NULL)",
            name="cep_fields_required",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    radius_km: Mapped[int] = mapped_column(Integer, nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class Venue(Base):
    """Local esportivo descoberto; catálogo vazio nesta fase."""

    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("kind IN ('public', 'private')", name="kind_valid"),
        CheckConstraint("lat BETWEEN -90 AND 90", name="lat_valid"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="lng_valid"),
        Index("ix_venues_city_state", "city", "state"),
        Index(
            "ix_venues_location_gist",
            text("(ST_SetSRID(ST_MakePoint(lng, lat), 4326))"),
            postgresql_using="gist",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
