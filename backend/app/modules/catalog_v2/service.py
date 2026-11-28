"""Serviços de catálogo v2 atrás da flag, sem endpoints nesta fase."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.catalog_v2.errors import (
    CatalogV2Disabled,
    CatalogV2PriceNotFound,
    CatalogV2ProductNotFound,
)
from app.modules.catalog_v2.pricing import (
    SEASON_PASS_KIND,
    PriceQuote,
    rate_bps,
    validate_installments,
)
from app.modules.catalog_v2.refund import (
    RefundCalculation,
    season_pass_refund,
    subscription_no_use_refund,
    subscription_refund,
)
from app.modules.catalog_v2.seed import get_active_product, get_price


def ensure_catalog_v2_enabled(settings: Settings) -> None:
    """Operações de catálogo v2 só rodam com a flag explícita ligada."""

    if not settings.catalog_v2_enabled:
        raise CatalogV2Disabled("catalog_v2_enabled está desligado")


def quote_for_product(
    session: Session,
    *,
    product_code: str,
    payment_method: str,
    installments: int,
    catalog_version: int | None = None,
) -> PriceQuote:
    """Resolve o preço no servidor a partir da tabela versionada.

    O cliente nunca envia valor: envia produto, meio e parcelas. O preço de
    tabela já armazenado é a autoridade, não um cálculo do request.
    """

    product = get_active_product(session, product_code)
    if product is None:
        raise CatalogV2ProductNotFound(product_code)
    validate_installments(product.kind, payment_method, installments)
    price = get_price(
        session,
        product,
        payment_method=payment_method,
        installments=installments,
        catalog_version=catalog_version,
    )
    if price is None:
        raise CatalogV2PriceNotFound(
            f"sem preço para {product_code} {payment_method} {installments}x"
        )
    unit_amount: int | None = None
    if product.kind == SEASON_PASS_KIND:
        actual_installments = installments
    else:
        actual_installments = 1
        if product.tickets_per_month:
            unit_amount = price.amount_cents // product.tickets_per_month
    return PriceQuote(
        product_code=product.code,
        kind=product.kind,
        payment_method=payment_method,
        installments=actual_installments,
        amount_cents=price.amount_cents,
        unit_amount_cents=unit_amount,
        rate_bps=rate_bps(payment_method, actual_installments),
        catalog_version=price.catalog_version,
    )


def price_snapshot(quote: PriceQuote) -> dict[str, Any]:
    """Snapshot imutável para congelar no contrato no momento da compra."""

    return {
        "product_code": quote.product_code,
        "kind": quote.kind,
        "payment_method": quote.payment_method,
        "installments": quote.installments,
        "amount_cents": quote.amount_cents,
        "unit_amount_cents": quote.unit_amount_cents,
        "rate_bps": quote.rate_bps,
        "catalog_version": quote.catalog_version,
    }


def calculate_subscription_refund(
    settings: Settings,
    *,
    unused_tickets: int,
    paid_unit_cents: int,
    payment_method: str,
    installments: int = 1,
) -> RefundCalculation:
    """Reembolso da assinatura, bloqueado enquanto a flag estiver desligada."""

    ensure_catalog_v2_enabled(settings)
    return subscription_refund(
        unused_tickets=unused_tickets,
        paid_unit_cents=paid_unit_cents,
        payment_method=payment_method,
        installments=installments,
    )


def calculate_subscription_no_use_refund(
    settings: Settings,
    *,
    paid_total_cents: int,
    payment_method: str,
    installments: int = 1,
    psp_refunded_fee: bool = False,
) -> RefundCalculation:
    """Reembolso de arrependimento sem uso, também atrás da flag."""

    ensure_catalog_v2_enabled(settings)
    return subscription_no_use_refund(
        paid_total_cents=paid_total_cents,
        payment_method=payment_method,
        installments=installments,
        psp_refunded_fee=psp_refunded_fee,
    )


def calculate_season_pass_refund(
    settings: Settings,
    *,
    months_unused: int,
    tickets_redeemed: int,
    payment_method: str,
    installments: int = 1,
) -> RefundCalculation:
    """Reembolso do passe, bloqueado enquanto a flag estiver desligada."""

    ensure_catalog_v2_enabled(settings)
    return season_pass_refund(
        months_unused=months_unused,
        tickets_redeemed=tickets_redeemed,
        payment_method=payment_method,
        installments=installments,
    )


__all__ = [
    "calculate_season_pass_refund",
    "calculate_subscription_no_use_refund",
    "calculate_subscription_refund",
    "ensure_catalog_v2_enabled",
    "price_snapshot",
    "quote_for_product",
]
