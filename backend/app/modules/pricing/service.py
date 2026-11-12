"""Resolução e validação de faixas de preço (ADR 0042 §3)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.pricing.models import PricingBand, PricingBandTicket


class PricingBandError(Exception):
    """Erro de faixa de preço."""


class PricingBandNotFound(PricingBandError):
    """A faixa informada não existe ou está inativa."""


class PriceAboveCeiling(PricingBandError):
    """O valor da quadra não cabe em nenhuma faixa ativa."""


class BandTicketsNotConfigured(PricingBandError):
    """A faixa não tem quantidade de ingressos para o formato."""


# Tabela 2D da ADR 0042 §3: ingressos por jogador, por faixa e tamanho de time.
BAND_TICKETS: dict[str, dict[int, int]] = {
    "economica_dia": {5: 5, 6: 4, 4: 6, 3: 8},
    "economica_noite": {5: 6, 6: 5, 4: 8, 3: 10},
    "padrao_dia": {5: 7, 6: 6, 4: 9, 3: 12},
    "padrao_noite": {5: 9, 6: 7, 4: 11, 3: 14},
    "coberta": {5: 10, 6: 9, 4: 13, 3: 17},
    "premium": {5: 12, 6: 10, 4: 14, 3: 19},
}


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
    seed_default_band_tickets(session)


def seed_default_band_tickets(session: Session, *, version: int = 1) -> None:
    """Garante a matriz faixa × tamanho de time. Idempotente."""

    bands = {
        band.code: band
        for band in session.scalars(
            select(PricingBand).where(PricingBand.version == version)
        ).all()
    }
    existing = set(
        session.execute(select(PricingBandTicket.band_id, PricingBandTicket.team_size)).all()
    )
    for code, by_team_size in BAND_TICKETS.items():
        band = bands.get(code)
        if band is None:
            continue
        for team_size, tickets in by_team_size.items():
            if (band.id, team_size) in existing:
                continue
            session.add(
                PricingBandTicket(
                    band_id=band.id,
                    team_size=team_size,
                    tickets=tickets,
                )
            )
    session.flush()


def tickets_for(session: Session, band_id: uuid.UUID, team_size: int) -> int:
    """Ingressos por jogador para a faixa e o formato."""

    row = session.scalars(
        select(PricingBandTicket).where(
            PricingBandTicket.band_id == band_id,
            PricingBandTicket.team_size == team_size,
        )
    ).first()
    if row is None:
        raise BandTicketsNotConfigured
    return row.tickets


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
