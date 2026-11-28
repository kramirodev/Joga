"""Preço de tabela e validação de parcelas do catálogo v2 (ADR 0079 §2).

Funções puras, em centavos e aritmética inteira. O gross-up é sempre calculado
no servidor; o cliente envia apenas produto, meio e parcelas.

Regras:
- assinatura mensal: somente 1x (Pix ou cartão);
- passe de temporada: Pix à vista, cartão 1x ou 3x;
- 6x nunca existe em nenhum produto;
- cartão = ``P_pix / (1 - s - 0,5%)`` arredondado para cima, onde ``s`` é 4,99%
  no 1x e 9,05% no 3x e os 0,5% são a provisão de chargeback;
- assinatura aplica o gross-up por ticket e multiplica pela franquia, como na
  tabela publicada (R$ 72,00 / 135,60 / 230,30). O passe aplica sobre o total.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.modules.catalog_v2.errors import CatalogV2InvalidPayment

BPS_DENOMINATOR = 10_000
PIX_RATE_BPS = 99
CARD_1X_RATE_BPS = 499
CARD_3X_RATE_BPS = 905
CHARGEBACK_PROVISION_BPS = 50

PIX_PRICE_CENTS = 4_250
SUBSCRIPTION_UNIT_PRICES_CENTS = (340, 320, 310)
SUBSCRIPTION_TICKETS = (20, 40, 70)
SUBSCRIPTION_CARD_TOTALS_CENTS = (7_200, 13_560, 23_030)
SEASON_PASS_CARD_1X_CENTS = 4_497
SEASON_PASS_CARD_3X_CENTS = 4_699

PAYMENT_METHODS = ("pix", "card")
SUBSCRIPTION_KIND = "subscription"
SEASON_PASS_KIND = "season_pass"


@dataclass(frozen=True)
class PriceQuote:
    """Preço de tabela resolvido pelo servidor para um produto."""

    product_code: str
    kind: str
    payment_method: str
    installments: int
    amount_cents: int
    unit_amount_cents: int | None
    rate_bps: int
    catalog_version: int


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def round_half_up_cents(value: Decimal) -> int:
    """Arredonda centavos para cima no empate, sem ponto flutuante."""

    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rate_bps(payment_method: str, installments: int) -> int:
    """Custo do meio pago pela JOGA, em bps, sem a provisão de chargeback."""

    if payment_method == "pix" and installments == 1:
        return PIX_RATE_BPS
    if payment_method == "card" and installments == 1:
        return CARD_1X_RATE_BPS
    if payment_method == "card" and installments == 3:
        return CARD_3X_RATE_BPS
    raise CatalogV2InvalidPayment("meio ou parcelamento inválido")


def gross_up_cents(
    pix_cents: int,
    payment_method: str,
    installments: int,
) -> int:
    """Preço de tabela do cartão a partir do Pix, arredondado para cima."""

    if pix_cents <= 0:
        raise ValueError("preço Pix deve ser positivo")
    if payment_method == "pix":
        if installments != 1:
            raise CatalogV2InvalidPayment("Pix é sempre à vista")
        return pix_cents
    if payment_method != "card":
        raise CatalogV2InvalidPayment("meio de pagamento inválido")
    if installments not in (1, 3):
        raise CatalogV2InvalidPayment("cartão aceita somente 1x ou 3x")
    rate = rate_bps(payment_method, installments)
    denominator = BPS_DENOMINATOR - rate - CHARGEBACK_PROVISION_BPS
    return _ceil_div(pix_cents * BPS_DENOMINATOR, denominator)


def validate_installments(
    kind: str,
    payment_method: str,
    installments: int,
) -> None:
    """Recusa parcela indeterminada, 6x e parcelamento fora do produto."""

    if payment_method not in PAYMENT_METHODS:
        raise CatalogV2InvalidPayment("meio de pagamento inválido")
    if isinstance(installments, bool) or not isinstance(installments, int):
        raise CatalogV2InvalidPayment("parcelamento inválido")
    if installments == 6:
        raise CatalogV2InvalidPayment("6x não existe em nenhum produto")
    if payment_method == "pix":
        if installments != 1:
            raise CatalogV2InvalidPayment("Pix é sempre à vista")
        return
    if kind == SUBSCRIPTION_KIND:
        if installments != 1:
            raise CatalogV2InvalidPayment("assinatura aceita somente 1x no cartão")
        return
    if kind == SEASON_PASS_KIND:
        if installments not in (1, 3):
            raise CatalogV2InvalidPayment("passe aceita somente 1x ou 3x no cartão")
        return
    raise CatalogV2InvalidPayment("tipo de produto inválido")


def split_installments(total_cents: int, installments: int) -> list[int]:
    """Divide em parcelas; o centavo restante vai para a última, como na ADR.

    Exemplo: R$ 46,99 em 3x = 15,66 + 15,66 + 15,67.
    """

    if total_cents <= 0:
        raise ValueError("total deve ser positivo")
    if installments not in (1, 3):
        raise CatalogV2InvalidPayment("parcelamento inválido")
    base, remainder = divmod(total_cents, installments)
    parts = [base for _ in range(installments)]
    parts[-1] += remainder
    return parts


def quote_subscription(
    *,
    product_code: str,
    unit_pix_cents: int,
    tickets_per_month: int,
    payment_method: str,
    installments: int,
    catalog_version: int,
) -> PriceQuote:
    """Preço da assinatura: gross-up por ticket × franquia mensal."""

    if tickets_per_month <= 0:
        raise ValueError("franquia mensal deve ser positiva")
    validate_installments(SUBSCRIPTION_KIND, payment_method, installments)
    unit_amount = (
        unit_pix_cents if payment_method == "pix" else gross_up_cents(unit_pix_cents, "card", 1)
    )
    return PriceQuote(
        product_code=product_code,
        kind=SUBSCRIPTION_KIND,
        payment_method=payment_method,
        installments=1,
        amount_cents=unit_amount * tickets_per_month,
        unit_amount_cents=unit_amount,
        rate_bps=rate_bps(payment_method, 1),
        catalog_version=catalog_version,
    )


def quote_season_pass(
    *,
    product_code: str,
    pix_total_cents: int,
    payment_method: str,
    installments: int,
    catalog_version: int,
) -> PriceQuote:
    """Preço do passe: gross-up sobre o total e 1x/3x no cartão."""

    validate_installments(SEASON_PASS_KIND, payment_method, installments)
    amount = (
        pix_total_cents
        if payment_method == "pix"
        else gross_up_cents(pix_total_cents, "card", installments)
    )
    return PriceQuote(
        product_code=product_code,
        kind=SEASON_PASS_KIND,
        payment_method=payment_method,
        installments=installments,
        amount_cents=amount,
        unit_amount_cents=None,
        rate_bps=rate_bps(payment_method, installments),
        catalog_version=catalog_version,
    )


__all__ = [
    "CARD_1X_RATE_BPS",
    "CARD_3X_RATE_BPS",
    "CHARGEBACK_PROVISION_BPS",
    "PAYMENT_METHODS",
    "PIX_PRICE_CENTS",
    "PIX_RATE_BPS",
    "PriceQuote",
    "SEASON_PASS_CARD_1X_CENTS",
    "SEASON_PASS_CARD_3X_CENTS",
    "SEASON_PASS_KIND",
    "SUBSCRIPTION_CARD_TOTALS_CENTS",
    "SUBSCRIPTION_KIND",
    "SUBSCRIPTION_TICKETS",
    "SUBSCRIPTION_UNIT_PRICES_CENTS",
    "gross_up_cents",
    "quote_season_pass",
    "quote_subscription",
    "rate_bps",
    "split_installments",
    "validate_installments",
]
