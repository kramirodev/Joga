"""Modelo de eventos operacionais de observabilidade (ADR 0078).

``log_events`` guarda HTTP, aplicação, jobs e clientes. Eventos de segurança e
auditoria continuam nas trilhas canônicas (``security_events`` e
``audit_logs``), que são estendidas de forma aditiva — não há segunda trilha de
auditoria.
"""

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
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

JsonType = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")

LOG_LEVELS = ("debug", "info", "warn", "error", "fatal")
LOG_CATEGORIES = ("http", "app", "security", "audit", "job", "client")


class LogEvent(Base):
    """Evento operacional append-only com retenção curta."""

    __tablename__ = "log_events"
    __table_args__ = (
        CheckConstraint(
            "level IN ('debug', 'info', 'warn', 'error', 'fatal')",
            name="level_valid",
        ),
        CheckConstraint(
            "category IN ('http', 'app', 'security', 'audit', 'job', 'client')",
            name="category_valid",
        ),
        Index(
            "ix_log_events_occurred_at",
            "occurred_at",
            postgresql_using="brin",
        ),
        Index("ix_log_events_level_occurred_at", "level", "occurred_at"),
        Index("ix_log_events_category_occurred_at", "category", "occurred_at"),
        Index("ix_log_events_request_id", "request_id"),
        Index("ix_log_events_user_occurred_at", "user_id", "occurred_at"),
        Index("ix_log_events_ip_hash_occurred_at", "ip_hash", "occurred_at"),
        Index("ix_log_events_status_occurred_at", "status", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="app")
    module: Mapped[str | None] = mapped_column(String(80), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column("metadata", JsonType, nullable=True)


__all__ = ["LOG_CATEGORIES", "LOG_LEVELS", "LogEvent"]
