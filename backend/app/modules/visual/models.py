"""Catálogo fechado de identidade visual e escolhas do jogador.

Não existe texto livre nem URL: cada slot aponta para um item do catálogo
aprovado. A exposição pública usa apenas icon/frame/accent/badge, nunca dados
pessoais.
"""

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
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

VISUAL_KINDS = ("icon", "frame", "accent", "entry", "emote", "badge")
VISUAL_UNLOCK_STATES = ("free", "xp", "pass")


class VisualCatalogItem(Base):
    """Item aprovado do catálogo de identidade visual."""

    __tablename__ = "visual_catalog_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('icon', 'frame', 'accent', 'entry', 'emote', 'badge')",
            name="kind_valid",
        ),
        CheckConstraint(
            "unlock_state IN ('free', 'xp', 'pass')",
            name="unlock_state_valid",
        ),
        UniqueConstraint("key", name="uq_visual_catalog_items_key"),
        Index("ix_visual_catalog_items_kind_active", "kind", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    season: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unlock_state: Mapped[str] = mapped_column(
        String(10), nullable=False, default="free", server_default=text("'free'")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class UserVisualIdentity(Base):
    """Seis slots equipados por usuário; substitui o avatar configurável."""

    __tablename__ = "user_visual_identity"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    icon_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    frame_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    accent_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    entry_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    emote_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    badge_key: Mapped[str] = mapped_column(
        ForeignKey("visual_catalog_items.key", ondelete="RESTRICT"), nullable=False
    )
    catalog_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class UserVisualUnlock(Base):
    """Desbloqueio explícito de um item que não é gratuito."""

    __tablename__ = "user_visual_unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_user_visual_unlocks_user_item"),
        Index("ix_user_visual_unlocks_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visual_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="xp", server_default=text("'xp'")
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
