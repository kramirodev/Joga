"""Versões de Termos de Uso com estado de revisão jurídica (ADR 0049 §5.4).

O texto é conteúdo, não código: o backend guarda a versão, o estado e a referência
da revisão. Aceite só pode apontar para versão ``approved``; versão publicada é
imutável — correção vira versão nova.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

TERMS_STATUSES = ("draft", "approved")


class TermsVersion(Base):
    """Versão de Termos de Uso. ``approved`` é o único estado aceitável."""

    __tablename__ = "terms_versions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'approved')", name="status_valid"),
        CheckConstraint(
            "status = 'approved' OR published_at IS NULL",
            name="published_requires_approval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    legal_review_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
