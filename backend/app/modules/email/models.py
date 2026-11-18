"""Modelos da credencial de e-mail e do log de entrega transacional (ADR 0050)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

EMAIL_DELIVERY_STATUSES = ("queued", "sent", "failed", "bounced")
EMAIL_KINDS = (
    "email_verification",
    "email_login",
    "email_change_confirm",
    "email_change_notice",
    "welcome",
    "security_alert",
    "account_deletion_notice",
    "password_reset",
    "password_changed",
)


class UserEmail(Base):
    """Credencial de e-mail verificada; autoridade do login por e-mail.

    ``users.email`` não é usada aqui: é o campo legado do pagador, sem
    normalização, sem verificação e sem autoridade de autenticação.
    """

    __tablename__ = "user_emails"
    __table_args__ = (
        Index(
            "uq_user_emails_active_email",
            "email_normalized",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
        Index(
            "uq_user_emails_primary_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary AND released_at IS NULL"),
            sqlite_where=text("is_primary = 1 AND released_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email_normalized: Mapped[str] = mapped_column(String(254), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Contador de bounce permanente: após o limite, a credencial deixa de
    # autenticar até recuperação por passkey/suporte.
    hard_bounce_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    undeliverable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class EmailDelivery(Base):
    """Log de entrega sem corpo, código ou endereço completo.

    A chave de idempotência impede que uma repetição da Outbox envie o mesmo
    e-mail duas vezes. ``email_hash`` permite correlação sem guardar o endereço.
    """

    __tablename__ = "email_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'sent', 'failed', 'bounced')",
            name="status_valid",
        ),
        CheckConstraint(
            "kind IN ('email_verification', 'email_login', 'email_change_confirm', "
            "'email_change_notice', 'welcome', 'security_alert', "
            "'account_deletion_notice', 'password_reset', 'password_changed')",
            name="kind_valid",
        ),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_email_deliveries_user_created", "user_id", "created_at"),
        Index("ix_email_deliveries_kind_created", "kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default="queued"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    last_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


__all__ = [
    "EMAIL_DELIVERY_STATUSES",
    "EMAIL_KINDS",
    "EmailDelivery",
    "UserEmail",
]
