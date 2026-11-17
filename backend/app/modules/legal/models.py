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
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

TERMS_STATUSES = ("draft", "approved")
TERMS_ACCEPTANCE_CONTEXTS = (
    "signup",
    "credit_purchase",
    "pass_purchase",
    "booking_ceiling",
)


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


class TermsAcceptance(Base):
    """Prova de aceite de uma versão aprovada, por usuário e contexto.

    ``terms_hash`` prova o conteúdo mostrado mesmo que a versão mude; ``ip_hash``
    é HMAC, nunca IP em claro. O par usuário/versão/contexto é idempotente.
    """

    __tablename__ = "terms_acceptances"
    __table_args__ = (
        CheckConstraint(
            "context IN ('signup', 'credit_purchase', 'pass_purchase', 'booking_ceiling')",
            name="context_valid",
        ),
        UniqueConstraint(
            "user_id",
            "terms_version_id",
            "context",
            name="uq_terms_acceptances_user_version_context",
        ),
        Index("ix_terms_acceptances_user_accepted", "user_id", "accepted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    terms_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms_versions.id", ondelete="RESTRICT"), nullable=False
    )
    context: Mapped[str] = mapped_column(String(20), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    terms_hash: Mapped[str] = mapped_column(String(64), nullable=False)
