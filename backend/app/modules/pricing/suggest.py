"""Preço automático por faixa e override administrativo (ADR 0042/0049).

A fórmula vigente é ``k = ceil(1.2 * teto_cents / (2 * team_size * 310))``.
Para formatos fora de 3x3, 5x5 e 6x6 a operação precisa escolher explicitamente
entre o padrão com 20% e a contingência sem 20%; nada é inferido.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.pricing.models import PricingBand, PricingBandTicket
from app.modules.pricing.service import STANDARD_TEAM_SIZES, TICKET_CALIBRATION_CENTS


class PricingSuggestionError(Exception):
    """Erro base do cálculo/override de preço."""


class InvalidPricingTeamSize(PricingSuggestionError):
    """Tamanho de time inválido para o cálculo."""


class PricingModeRequired(PricingSuggestionError):
    """Formato não padrão exige escolha explícita de modo."""


class InvalidPricingMode(PricingSuggestionError):
    """Modo diferente de standard/contingency."""


class InvalidBandTicketsFloor(PricingSuggestionError):
    """Override tentou ficar abaixo do número mínimo de tickets."""


class PricingBandNotFound(PricingSuggestionError):
    """Faixa ativa inexistente."""


PRICING_MODES = ("standard", "contingency")
MARGIN_NUMERATOR = 6  # 1,2 = 6/5
MARGIN_DENOMINATOR = 5


@dataclass(frozen=True)
class BandSuggestion:
    code: str
    label: str
    max_price_cents: int
    tickets: int
    player_price_cents: int
    invariant_ok: bool


@dataclass(frozen=True)
class PricingSuggestion:
    team_size: int
    mode: str
    calibration_cents: int
    bands: list[BandSuggestion]


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def resolve_mode(team_size: int, mode: str | None) -> str:
    """Resolve o modo sem adivinhar: fora de 3/5/6 ele é obrigatório."""

    if team_size <= 0 or team_size > 20:
        raise InvalidPricingTeamSize
    if mode is not None and mode not in PRICING_MODES:
        raise InvalidPricingMode
    if team_size in STANDARD_TEAM_SIZES:
        return mode or "standard"
    if mode is None:
        raise PricingModeRequired
    return mode


def suggested_tickets(*, max_price_cents: int, team_size: int, mode: str) -> int:
    if max_price_cents <= 0:
        raise InvalidPricingTeamSize
    if team_size <= 0:
        raise InvalidPricingTeamSize
    if mode not in PRICING_MODES:
        raise InvalidPricingMode
    denominator = 2 * team_size * TICKET_CALIBRATION_CENTS
    if mode == "standard":
        return _ceil_div(MARGIN_NUMERATOR * max_price_cents, MARGIN_DENOMINATOR * denominator)
    return _ceil_div(max_price_cents, denominator)


def invariant_holds(*, max_price_cents: int, team_size: int, tickets: int, mode: str) -> bool:
    denominator = 2 * team_size
    if mode == "standard":
        # k*310 >= 1,2*V/(2*team)  <=>  10*team*310*k >= 6*V
        return 10 * team_size * TICKET_CALIBRATION_CENTS * tickets >= (
            MARGIN_NUMERATOR * max_price_cents
        )
    return denominator * TICKET_CALIBRATION_CENTS * tickets >= max_price_cents


def active_bands(session: Session) -> list[PricingBand]:
    latest = session.scalar(
        select(PricingBand.version).order_by(PricingBand.version.desc()).limit(1)
    )
    if latest is None:
        return []
    return list(
        session.scalars(
            select(PricingBand)
            .where(PricingBand.active.is_(True), PricingBand.version == latest)
            .order_by(PricingBand.max_price_cents.asc())
        )
    )


def build_suggestion(session: Session, *, team_size: int, mode: str | None) -> PricingSuggestion:
    resolved = resolve_mode(team_size, mode)
    bands = active_bands(session)
    if not bands:
        raise PricingBandNotFound
    suggestions = []
    for band in bands:
        tickets = suggested_tickets(
            max_price_cents=band.max_price_cents,
            team_size=team_size,
            mode=resolved,
        )
        suggestions.append(
            BandSuggestion(
                code=band.code,
                label=band.label,
                max_price_cents=band.max_price_cents,
                tickets=tickets,
                player_price_cents=tickets * TICKET_CALIBRATION_CENTS,
                invariant_ok=invariant_holds(
                    max_price_cents=band.max_price_cents,
                    team_size=team_size,
                    tickets=tickets,
                    mode=resolved,
                ),
            )
        )
    return PricingSuggestion(
        team_size=team_size,
        mode=resolved,
        calibration_cents=TICKET_CALIBRATION_CENTS,
        bands=suggestions,
    )


def minimum_tickets(session: Session, *, team_size: int, band: PricingBand, mode: str) -> int:
    return suggested_tickets(
        max_price_cents=band.max_price_cents,
        team_size=team_size,
        mode=mode,
    )


def pricing_configured(session: Session, team_size: int) -> bool:
    """Todas as faixas ativas têm célula para o formato e respeitam a fórmula."""

    bands = active_bands(session)
    if not bands:
        return False
    # O modo não é persistido na matriz. Formatos padrão usam o piso com 20%;
    # os demais usam o piso de contingência (sem 20%).
    mode = "standard" if team_size in STANDARD_TEAM_SIZES else "contingency"
    for band in bands:
        row = session.scalar(
            select(PricingBandTicket).where(
                PricingBandTicket.band_id == band.id,
                PricingBandTicket.team_size == team_size,
            )
        )
        if row is None:
            return False
        if not invariant_holds(
            max_price_cents=band.max_price_cents,
            team_size=team_size,
            tickets=row.tickets,
            mode=mode,
        ):
            return False
    return True


def override_band_tickets(
    session: Session,
    *,
    band_code: str,
    team_size: int,
    tickets: int,
    mode: str | None,
) -> PricingBandTicket:
    """Grava override acima do piso; nunca aceita valor que quebre o invariante."""

    resolved = resolve_mode(team_size, mode)
    bands = active_bands(session)
    band = next((item for item in bands if item.code == band_code), None)
    if band is None:
        raise PricingBandNotFound
    floor = minimum_tickets(session, team_size=team_size, band=band, mode=resolved)
    if tickets < floor:
        raise InvalidBandTicketsFloor
    if not invariant_holds(
        max_price_cents=band.max_price_cents,
        team_size=team_size,
        tickets=tickets,
        mode=resolved,
    ):
        raise InvalidBandTicketsFloor

    row = session.scalar(
        select(PricingBandTicket).where(
            PricingBandTicket.band_id == band.id,
            PricingBandTicket.team_size == team_size,
        )
    )
    if row is None:
        row = PricingBandTicket(band_id=band.id, team_size=team_size, tickets=tickets)
        session.add(row)
    else:
        row.tickets = tickets
    session.flush()
    return row


__all__ = [
    "BandSuggestion",
    "InvalidBandTicketsFloor",
    "InvalidPricingMode",
    "InvalidPricingTeamSize",
    "PRICING_MODES",
    "PricingBandNotFound",
    "PricingModeRequired",
    "PricingSuggestion",
    "PricingSuggestionError",
    "build_suggestion",
    "override_band_tickets",
    "pricing_configured",
    "resolve_mode",
    "suggested_tickets",
]
