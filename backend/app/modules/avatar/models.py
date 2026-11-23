"""Avatar do jogador: uma linha por usuário, arquivo em storage privado.

A tabela é separada de ``user_profiles`` porque o arquivo, a origem e a
temporalidade da importação são um contrato próprio e não devem contaminar a
leitura do perfil esportivo. A identidade visual por presets continua em
``user_visual_identity``; esta tabela só existe quando há uma foto real.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

AVATAR_SOURCES = ("instagram_scrape", "preset", "upload")


class UserAvatar(Base):
    """Foto de avatar do jogador e metadados mínimos da importação."""

    __tablename__ = "user_avatars"
    __table_args__ = (
        CheckConstraint(
            "source IN ('instagram_scrape', 'preset', 'upload')",
            name="source_valid",
        ),
        CheckConstraint(
            "source <> 'instagram_scrape' OR (storage_key IS NOT NULL AND imported_at IS NOT NULL)",
            name="instagram_scrape_complete",
        ),
        CheckConstraint(
            "storage_key IS NULL OR "
            "(content_type IS NOT NULL AND size_bytes IS NOT NULL "
            "AND width IS NOT NULL AND height IS NOT NULL)",
            name="storage_fields_complete",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="size_non_negative",
        ),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="width_positive",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="height_positive",
        ),
    )

    # A chave primária já garante um único avatar por usuário.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # ``source_url`` é a página pública informada pelo próprio jogador. Nunca é
    # a URL assinada da CDN: essa não é persistida nem auditada.
    source_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
