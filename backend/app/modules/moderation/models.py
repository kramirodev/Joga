"""Denúncias, triagem e medidas de moderação (Fase 17A)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

REPORT_CATEGORIES = ("HARASSMENT", "HATE", "THREAT", "SEXUAL", "SPAM", "OTHER")
REPORT_STATUSES = ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED", "APPEALED")
REPORT_SEVERITIES = ("LOW", "MEDIUM", "HIGH")
ACTION_TYPES = ("WARNING", "RESTRICT_RANKED", "SUSPEND_TEMP")
ACTION_STATUSES = ("ACTIVE", "REVOKED", "EXPIRED")


class ModerationReport(Base):
    """Denúncia textual com contexto limitado do lobby."""

    __tablename__ = "moderation_reports"
    __table_args__ = (
        CheckConstraint(
            "category IN ('HARASSMENT','HATE','THREAT','SEXUAL','SPAM','OTHER')",
            name="category_valid",
        ),
        CheckConstraint(
            "status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED','APPEALED')",
            name="status_valid",
        ),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH')", name="severity_valid"),
        CheckConstraint("priority BETWEEN 0 AND 100", name="priority_valid"),
        CheckConstraint(
            "length(description) BETWEEN 1 AND 2000",
            name="description_length_valid",
        ),
        Index("ix_moderation_reports_target_created", "target_user_id", "created_at"),
        Index("ix_moderation_reports_status_priority", "status", "priority"),
        Index("ix_moderation_reports_reporter_created", "reporter_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", server_default="OPEN"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(40), nullable=False)
    classifier_signals: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModerationAction(Base):
    """Medida reversível aplicada a uma denúncia."""

    __tablename__ = "moderation_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('WARNING','RESTRICT_RANKED','SUSPEND_TEMP')",
            name="type_valid",
        ),
        CheckConstraint("status IN ('ACTIVE','REVOKED','EXPIRED')", name="status_valid"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="time_order_valid"),
        Index("ix_moderation_actions_target_status", "target_user_id", "status"),
        Index("ix_moderation_actions_report", "report_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_reports.id", ondelete="CASCADE"), nullable=False
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModerationAppeal(Base):
    """Recurso do jogador contra uma medida, com decisão humana separada."""

    __tablename__ = "moderation_appeals"
    __table_args__ = (
        UniqueConstraint("action_id", "user_id", name="uq_moderation_appeals_action_user"),
        CheckConstraint("status IN ('OPEN','ACCEPTED','REJECTED')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_actions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", server_default="OPEN"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "ACTION_STATUSES",
    "ACTION_TYPES",
    "ModerationAction",
    "ModerationAppeal",
    "ModerationReport",
    "REPORT_CATEGORIES",
    "REPORT_SEVERITIES",
    "REPORT_STATUSES",
]
