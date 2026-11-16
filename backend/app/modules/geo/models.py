"""Modelos de geocodificação de CEP (Fase 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow


class PostalCodeCache(Base):
    """Cache persistente de CEP resolvido, com TTL controlado."""

    __tablename__ = "postal_code_cache"
    __table_args__ = (
        Index("ix_postal_code_cache_expires_at", "expires_at"),
        Index("ix_postal_code_cache_postal_code", "postal_code"),
    )

    cache_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    postal_code: Mapped[str] = mapped_column(String(8), nullable=False)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
