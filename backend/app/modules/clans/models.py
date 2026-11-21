"""Modelos de clã, membros, pedidos, chat, denúncias e troféus (Fase 16)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

CLAN_ROLES = ("owner", "admin", "member")
MEMBER_STATUSES = ("active", "left", "removed")
JOIN_POLICIES = ("approval", "open", "closed")
REQUEST_STATUSES = ("pending", "approved", "rejected", "cancelled")
INVITE_STATUSES = ("pending", "accepted", "declined", "expired")
REPORT_STATUSES = ("OPEN", "KEEP_HIDDEN", "RESTORED", "DISMISSED")


class Clan(Base):
    """Clã do MVP. Entrada por aprovação, no máximo 30 membros."""

    __tablename__ = "clans"
    __table_args__ = (
        CheckConstraint("join_policy IN ('approval', 'open', 'closed')", name="join_policy_valid"),
        CheckConstraint("status IN ('active', 'archived')", name="status_valid"),
        CheckConstraint("length(name) BETWEEN 3 AND 40", name="name_length_valid"),
        CheckConstraint(
            "length(tag) BETWEEN 3 AND 8 AND substr(tag, 1, 1) = '#'",
            name="tag_length_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    tag: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(280), nullable=True)
    emblem_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    join_policy: Mapped[str] = mapped_column(
        String(12), nullable=False, default="approval", server_default=text("'approval'")
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="active", server_default=text("'active'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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


class ClanMember(Base):
    """Vínculo do jogador com o clã. Um clã ativo por jogador."""

    __tablename__ = "clan_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="role_valid"),
        CheckConstraint("status IN ('active', 'left', 'removed')", name="status_valid"),
        Index("ix_clan_members_user_status", "user_id", "status"),
        Index(
            "uq_clan_members_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        String(10), nullable=False, default="member", server_default=text("'member'")
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active", server_default=text("'active'")
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClanJoinRequest(Base):
    """Pedido de entrada. A aprovação é sempre humana."""

    __tablename__ = "clan_join_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="status_valid",
        ),
        Index("ix_clan_join_requests_clan_status", "clan_id", "status"),
        Index(
            "uq_clan_join_requests_pending",
            "clan_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pending", server_default=text("'pending'")
    )
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class ClanInvite(Base):
    """Convite direto de um clã para um amigo aceito.

    Só o dono ou um admin convida, e só para um amigo não bloqueado. O convite
    tem prazo de sete dias; aceitar exige que o jogador não tenha clã ativo. O
    índice único parcial impede dois convites pendentes do mesmo clã para a
    mesma pessoa sem apagar o histórico de respostas.
    """

    __tablename__ = "clan_invites"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired')",
            name="status_valid",
        ),
        CheckConstraint("inviter_id <> invitee_id", name="distinct_users"),
        Index("ix_clan_invites_invitee_status", "invitee_id", "status"),
        Index("ix_clan_invites_clan_status", "clan_id", "status"),
        Index(
            "uq_clan_invites_pending",
            "clan_id",
            "invitee_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClanTrophyEvent(Base):
    """Ponto de troféu por partida e jogador. Append-only e idempotente."""

    __tablename__ = "clan_trophy_events"
    __table_args__ = (
        CheckConstraint("points >= 0", name="points_non_negative"),
        UniqueConstraint("match_id", "user_id", name="uq_clan_trophy_match_user"),
        Index("ix_clan_trophy_clan_season_format", "clan_id", "season_id", "format_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class ClanTrophySnapshot(Base):
    """Fechamento auditável dos troféus de um clã por temporada e formato."""

    __tablename__ = "clan_trophy_snapshots"
    __table_args__ = (
        CheckConstraint("points >= 0", name="points_non_negative"),
        UniqueConstraint(
            "clan_id",
            "season_id",
            "format_id",
            name="uq_clan_trophy_snapshot",
        ),
        Index("ix_clan_trophy_snapshot_season", "season_id", "format_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sport_formats.id", ondelete="CASCADE"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class ClanMessage(Base):
    """Mensagem do chat do clã. Ocultação é marca de moderação, não exclusão."""

    __tablename__ = "clan_messages"
    __table_args__ = (
        CheckConstraint("length(body) BETWEEN 1 AND 2000", name="body_length_valid"),
        Index("ix_clan_messages_clan_created", "clan_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class ClanReport(Base):
    """Denúncia de mensagem. Ocultação é imediata; a revisão vem depois."""

    __tablename__ = "clan_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'KEEP_HIDDEN', 'RESTORED', 'DISMISSED')",
            name="status_valid",
        ),
        UniqueConstraint("message_id", "reporter_id", name="uq_clan_report_message_reporter"),
        Index("ix_clan_reports_clan_status", "clan_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clan_messages.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(
        String(14), nullable=False, default="OPEN", server_default=text("'OPEN'")
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
