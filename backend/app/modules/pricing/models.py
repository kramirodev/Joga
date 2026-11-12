"""Faixas de preço da tabela 2D (ADR 0042 §3, Fase 14D.1).

A faixa é um degrau de preço: cada linha da tabela 2D cobre um intervalo de
valor de quadra e determina quantos ingressos a partida consome. A faixa é
versionada para que a reserva possa gravar a versão usada.
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


class PricingBand(Base):
    """Degrau de preço: teto em centavos, rótulo visível e versão."""

    __tablename__ = "pricing_bands"
    __table_args__ = (
        CheckConstraint("max_price_cents > 0", name="max_price_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("code", "version", name="uq_pricing_bands_code_version"),
        Index("ix_pricing_bands_active_ceiling", "active", "max_price_cents"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    max_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PricingBandTicket(Base):
    """Quantos ingressos cada jogador gasta, por faixa e tamanho de time.

    É a tabela 2D da ADR 0042 §3: a faixa define o preço, o formato define a
    divisão entre os jogadores.
    """

    __tablename__ = "pricing_band_tickets"
    __table_args__ = (
        CheckConstraint("team_size > 0", name="team_size_positive"),
        CheckConstraint("tickets > 0", name="tickets_positive"),
        UniqueConstraint("band_id", "team_size", name="uq_pricing_band_tickets"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    band_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pricing_bands.id", ondelete="CASCADE"), nullable=False
    )
    team_size: Mapped[int] = mapped_column(Integer, nullable=False)
    tickets: Mapped[int] = mapped_column(Integer, nullable=False)
