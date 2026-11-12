"""Resolução e validação de faixas de preço (ADR 0042 §3)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.pricing.models import PricingBand


class PricingBandError(Exception):
    """Erro de faixa de preço."""


class PricingBandNotFound(PricingBandError):
    """A faixa informada não existe ou está inativa."""


class PriceAboveCeiling(PricingBandError):
    """O valor da quadra não cabe em nenhuma faixa ativa."""


DEFAULT_BANDS: tuple[tuple[str, str, int], ...] = (
    ("economica_dia", "Econômica dia", 12_000),
    ("economica_noite", "Econômica noite", 15_000),
    ("padrao_dia", "Padrão dia", 18_000),
    ("padrao_noite", "Padrão noite", 22_000),
    ("coberta", "Coberta", 26_000),
    ("premium", "Premium", 30_000),
)


def seed_default_bands(session: Session, *, version: int = 1) -> None:
    """Garante as faixas da tabela 2D. Idempotente.

    A migração já insere as faixas em produção; testes que criam o schema
    direto pelo metadata precisam chamar isto.
    """
    existing = set(
        session.scalars(select(PricingBand.code).where(PricingBand.version == version)).all()
    )
    for code, label, ceiling in DEFAULT_BANDS:
        if code in existing:
            continue
        session.add(
            PricingBand(
                code=code,
                label=label,
                max_price_cents=ceiling,
                version=version,
            )
        )
    session.flush()


def list_active_bands(session: Session) -> Sequence[PricingBand]:
    """Faixas ativas, da mais barata para a mais cara."""
    return session.scalars(
        select(PricingBand)
        .where(PricingBand.active.is_(True))
        .order_by(PricingBand.max_price_cents.asc())
    ).all()


def get_band(session: Session, band_id: uuid.UUID) -> PricingBand:
    band = session.get(PricingBand, band_id)
    if band is None or not band.active:
        raise PricingBandNotFound
    return band


def resolve_band(session: Session, price_cents: int) -> PricingBand:
    """Menor faixa ativa cujo teto cobre o valor da quadra.

    A resolução é por teto, não por escolha: isso impede que o estabelecimento
    se classifique numa faixa mais cara que o próprio preço para aumentar a
    margem às custas do jogador.
    """
    if price_cents <= 0:
        raise PriceAboveCeiling
    band = session.scalars(
        select(PricingBand)
        .where(
            PricingBand.active.is_(True),
            PricingBand.max_price_cents >= price_cents,
        )
        .order_by(PricingBand.max_price_cents.asc())
        .limit(1)
    ).first()
    if band is None:
        raise PriceAboveCeiling
    return band
