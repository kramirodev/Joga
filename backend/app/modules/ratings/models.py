"""Modelos de rating competitivo e Trust Factor."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

ALGORITHM_VERSION = "glicko2_team_v1"
RESULTS = ("WIN", "LOSS", "DRAW")


class RatingAccount(Base):
    """Estado atual do MMR de um usuário em um formato."""

    __tablename__ = "rating_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "format_id", name="uq_rating_account_user_format"),
        CheckConstraint("rating_deviation >= 0", name="rating_deviation_non_negative"),
        CheckConstraint("volatility > 0", name="volatility_positive"),
        CheckConstraint("matches_played >= 0", name="matches_played_non_negative"),
        Index("ix_rating_account_format_rating", "format_id", "rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=1500.0)
    rating_deviation: Mapped[float] = mapped_column(Float, nullable=False, default=350.0)
    volatility: Mapped[float] = mapped_column(Float, nullable=False, default=0.06)
    matches_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default=ALGORITHM_VERSION
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


class RatingEvent(Base):
    """Evento append-only de aplicação de MMR."""

    __tablename__ = "rating_events"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "user_id",
            "algorithm_version",
            name="uq_rating_event_match_user_version",
        ),
        CheckConstraint("result IN ('WIN', 'LOSS', 'DRAW')", name="result_valid"),
        CheckConstraint("rating_deviation_before >= 0", name="rd_before_non_negative"),
        CheckConstraint("rating_deviation_after >= 0", name="rd_after_non_negative"),
        CheckConstraint("volatility_before > 0", name="volatility_before_positive"),
        CheckConstraint("volatility_after > 0", name="volatility_after_positive"),
        Index(
            "ix_rating_event_user_format_created",
            "user_id",
            "format_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    rating_before: Mapped[float] = mapped_column(Float, nullable=False)
    rating_after: Mapped[float] = mapped_column(Float, nullable=False)
    rating_deviation_before: Mapped[float] = mapped_column(Float, nullable=False)
    rating_deviation_after: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_before: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_after: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class TrustAccount(Base):
    """Score interno de confiança; oculto e sem penalidade automática."""

    __tablename__ = "trust_accounts"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="score_range_valid"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class TrustEvent(Base):
    """Sinal auditável de confiança, sem exposição pública."""

    __tablename__ = "trust_events"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 0 AND 5", name="severity_range_valid"),
        Index("ix_trust_event_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    details: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
