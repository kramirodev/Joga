"""Modelos de identidade da Fase 3.

O subconjunto cobre usuário, telefone protegido, desafios OTP, dispositivos,
credenciais de passkey, sessões e trilhas de segurança/auditoria.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow
from app.modules.identity.tags import default_user_tag

USER_STATUSES = ("pending", "active", "suspended", "deleted")
CHALLENGE_PURPOSES = (
    "registration",
    "login",
    "phone_change",
    "recovery",
    "email_verification",
    "email_login",
    "email_change",
    "password_reset",
)
CHALLENGE_SUBJECT_TYPES = ("phone", "email")
DEVICE_PLATFORMS = ("android", "ios", "web", "unknown")


class User(Base):
    """Identidade central; o UUID é a referência interna, nunca o telefone."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'deleted')",
            name="status_valid",
        ),
        Index("uq_users_tag", "tag", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Identificador público curto: '#' + 8/10/12 hex maiúsculos derivados do
    # UUID. É único e nunca substitui autorização (ADR de identidade do jogador).
    tag: Mapped[str] = mapped_column(String(13), nullable=False, default=default_user_tag)
    # Legado do pagador: sem unique, sem normalização e sem autoridade de
    # login. A credencial de e-mail vive em ``user_emails`` (ADR 0050).
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class UserPhone(Base):
    """Telefone verificado, guardado apenas como hash de busca nesta iteração."""

    __tablename__ = "user_phones"
    __table_args__ = (
        Index(
            "uq_user_phones_active_hash",
            "phone_hash",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class UserPassword(Base):
    """Credencial de senha separada da credencial de e-mail (ADR 0050).

    Guarda apenas a string PHC do Argon2id. Nunca registra senha ou hash em
    respostas, logs ou auditoria.
    """

    __tablename__ = "user_passwords"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    compromised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PhoneChallenge(Base):
    """Desafio OTP de uso único; guarda apenas o HMAC do código.

    A tabela é compartilhada por telefone e e-mail (ADR 0050).
    ``phone_hash`` guarda o HMAC do sujeito com rótulo próprio para cada tipo,
    e ``subject_type`` torna a origem explícita.
    """

    __tablename__ = "phone_challenges"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('registration', 'login', 'phone_change', 'recovery', "
            "'email_verification', 'email_login', 'email_change', 'password_reset')",
            name="purpose_valid",
        ),
        CheckConstraint("subject_type IN ('phone', 'email')", name="subject_type_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        Index("ix_phone_challenges_phone_created", "phone_hash", "created_at"),
        Index(
            "ix_phone_challenges_subject_created",
            "subject_type",
            "phone_hash",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="phone", server_default="phone"
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    request_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class Device(Base):
    """Dispositivo vinculado ao usuário, com sinais mínimos."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('android', 'ios', 'web', 'unknown')",
            name="platform_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasskeyCredential(Base):
    """Credencial pública de passkey; nunca guarda chave privada."""

    __tablename__ = "passkey_credentials"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    credential_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transports: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasskeyChallenge(Base):
    """Desafio WebAuthn de uso único para registro ou autenticação."""

    __tablename__ = "passkey_challenges"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('registration', 'authentication')",
            name="purpose_valid",
        ),
        Index("uq_passkey_challenges_challenge", "challenge", unique=True),
        Index("ix_passkey_challenges_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class Session(Base):
    """Sessão com refresh opaco armazenado apenas como hash."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_revoked", "user_id", "revoked_at"),
        Index("uq_sessions_access_token_hash", "access_token_hash", unique=True),
        CheckConstraint(
            "revoked_reason IS NULL OR length(revoked_reason) <= 40",
            name="revoked_reason_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    replaced_by_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class SecurityEvent(Base):
    """Evento de autenticação/abuso; IP completo só para admin (ADR 0078)."""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_type_created", "event_type", "created_at"),
        Index("ix_security_events_ip_created", "ip", "created_at"),
        Index("ix_security_events_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class AuditLog(Base):
    """Trilha append-only de ações administrativas e sensíveis."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_ip_created", "ip", "created_at"),
        Index("ix_audit_logs_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
