"""Cálculo puro de reembolso proporcional ao não usado (ADR 0079 §6).

A regra é decisão do dono, com risco CDC registrado. O cálculo é reversível por
configuração e não expõe endpoint nesta fase. Nenhum resultado é negativo.

- Assinatura: ``não_usados × P_pago × (1 - s)``.
- Passe: ``(meses_não_usados / 3) × R$ 42,50 - tickets_resgatados × R$ 2,50 -
  taxa do meio``, limitado a zero.
- A provisão de 0,5% de chargeback não entra no ``s``; fica retida.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.catalog_v2.pricing import (
    BPS_DENOMINATOR,
    PIX_PRICE_CENTS,
    SEASON_PASS_KIND,
    SUBSCRIPTION_KIND,
    rate_bps,
    round_half_up_cents,
    validate_installments,
)

PASS_TICKET_DEDUCTION_CENTS = 250
PASS_MONTHS = 3


@dataclass(frozen=True)
class RefundCalculation:
    """Resultado auditável do cálculo de reembolso."""

    kind: str
    payment_method: str
    installments: int
    gross_cents: int
    rate_bps: int
    fee_cents: int
    tickets_deduction_cents: int
    net_cents: int


def _fee_cents(base_cents: int, bps: int) -> int:
    return round_half_up_cents(Decimal(base_cents * bps) / Decimal(BPS_DENOMINATOR))


def subscription_refund(
    *,
    unused_tickets: int,
    paid_unit_cents: int,
    payment_method: str,
    installments: int = 1,
) -> RefundCalculation:
    """Reembolso da assinatura pelo preço unitário efetivamente pago."""

    if unused_tickets < 0:
        raise ValueError("tickets não usados não pode ser negativo")
    if paid_unit_cents <= 0:
        raise ValueError("preço pago por ticket deve ser positivo")
    validate_installments(SUBSCRIPTION_KIND, payment_method, installments)
    bps = rate_bps(payment_method, 1)
    gross = unused_tickets * paid_unit_cents
    fee = _fee_cents(gross, bps)
    return RefundCalculation(
        kind=SUBSCRIPTION_KIND,
        payment_method=payment_method,
        installments=1,
        gross_cents=gross,
        rate_bps=bps,
        fee_cents=fee,
        tickets_deduction_cents=0,
        net_cents=max(0, gross - fee),
    )


def subscription_no_use_refund(
    *,
    paid_total_cents: int,
    payment_method: str,
    installments: int = 1,
    psp_refunded_fee: bool = False,
) -> RefundCalculation:
    """Reembolso dos 7 dias sem uso; o PSP pode devolver a taxa ou não."""

    if paid_total_cents <= 0:
        raise ValueError("valor pago deve ser positivo")
    validate_installments(SUBSCRIPTION_KIND, payment_method, installments)
    bps = rate_bps(payment_method, 1)
    fee = 0 if psp_refunded_fee else _fee_cents(paid_total_cents, bps)
    return RefundCalculation(
        kind=SUBSCRIPTION_KIND,
        payment_method=payment_method,
        installments=1,
        gross_cents=paid_total_cents,
        rate_bps=bps,
        fee_cents=fee,
        tickets_deduction_cents=0,
        net_cents=max(0, paid_total_cents - fee),
    )


def season_pass_refund(
    *,
    months_unused: int,
    tickets_redeemed: int,
    payment_method: str,
    installments: int = 1,
) -> RefundCalculation:
    """Reembolso do passe; exemplo da ADR: 1 mês usado e 6 tickets → R$ 13,33."""

    if not 0 <= months_unused <= PASS_MONTHS:
        raise ValueError("meses não usados deve estar entre 0 e 3")
    if tickets_redeemed < 0:
        raise ValueError("tickets resgatados não pode ser negativo")
    validate_installments(SEASON_PASS_KIND, payment_method, installments)
    bps = rate_bps(payment_method, installments)
    gross = round_half_up_cents(Decimal(PIX_PRICE_CENTS * months_unused) / Decimal(PASS_MONTHS))
    fee = _fee_cents(gross, bps)
    deduction = tickets_redeemed * PASS_TICKET_DEDUCTION_CENTS
    return RefundCalculation(
        kind=SEASON_PASS_KIND,
        payment_method=payment_method,
        installments=installments,
        gross_cents=gross,
        rate_bps=bps,
        fee_cents=fee,
        tickets_deduction_cents=deduction,
        net_cents=max(0, gross - fee - deduction),
    )


__all__ = [
    "PASS_MONTHS",
    "PASS_TICKET_DEDUCTION_CENTS",
    "RefundCalculation",
    "season_pass_refund",
    "subscription_no_use_refund",
    "subscription_refund",
]
