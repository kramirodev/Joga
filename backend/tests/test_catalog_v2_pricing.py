"""Preço de tabela, gross-up e validação de parcelas do catálogo v2 (ADR 0079)."""

from __future__ import annotations

import pytest

from app.modules.catalog_v2.errors import CatalogV2InvalidPayment
from app.modules.catalog_v2.pricing import (
    CARD_1X_RATE_BPS,
    CARD_3X_RATE_BPS,
    PIX_RATE_BPS,
    SEASON_PASS_CARD_1X_CENTS,
    SEASON_PASS_CARD_3X_CENTS,
    gross_up_cents,
    quote_season_pass,
    quote_subscription,
    rate_bps,
    split_installments,
    validate_installments,
)


def test_assinatura_bate_com_a_tabela_pix_e_cartao_1x() -> None:
    expected = (
        (340, 20, 6_800, 7_200, 360),
        (320, 40, 12_800, 13_560, 339),
        (310, 70, 21_700, 23_030, 329),
    )
    for unit_pix, tickets, pix_total, card_total, unit_card in expected:
        pix = quote_subscription(
            product_code="plano",
            unit_pix_cents=unit_pix,
            tickets_per_month=tickets,
            payment_method="pix",
            installments=1,
            catalog_version=2,
        )
        card = quote_subscription(
            product_code="plano",
            unit_pix_cents=unit_pix,
            tickets_per_month=tickets,
            payment_method="card",
            installments=1,
            catalog_version=2,
        )
        assert pix.amount_cents == pix_total
        assert pix.unit_amount_cents == unit_pix
        assert pix.installments == 1
        assert card.amount_cents == card_total
        assert card.unit_amount_cents == unit_card
        assert card.installments == 1


def test_passe_bate_com_a_tabela_4250_4497_4699() -> None:
    pix = quote_season_pass(
        product_code="passe",
        pix_total_cents=4_250,
        payment_method="pix",
        installments=1,
        catalog_version=2,
    )
    card_1x = quote_season_pass(
        product_code="passe",
        pix_total_cents=4_250,
        payment_method="card",
        installments=1,
        catalog_version=2,
    )
    card_3x = quote_season_pass(
        product_code="passe",
        pix_total_cents=4_250,
        payment_method="card",
        installments=3,
        catalog_version=2,
    )
    assert pix.amount_cents == 4_250
    assert card_1x.amount_cents == SEASON_PASS_CARD_1X_CENTS == 4_497
    assert card_3x.amount_cents == SEASON_PASS_CARD_3X_CENTS == 4_699
    assert split_installments(card_3x.amount_cents, 3) == [1_566, 1_566, 1_567]


def test_gross_up_arredonda_para_cima_e_nao_usa_ponto_flutuante() -> None:
    assert gross_up_cents(4_250, "card", 1) == 4_497
    assert gross_up_cents(4_250, "card", 3) == 4_699
    assert gross_up_cents(4_250, "pix", 1) == 4_250
    assert gross_up_cents(1, "card", 1) == 2
    with pytest.raises(ValueError):
        gross_up_cents(0, "card", 1)


def test_taxas_do_meio_sao_as_da_adr() -> None:
    assert rate_bps("pix", 1) == PIX_RATE_BPS == 99
    assert rate_bps("card", 1) == CARD_1X_RATE_BPS == 499
    assert rate_bps("card", 3) == CARD_3X_RATE_BPS == 905
    with pytest.raises(CatalogV2InvalidPayment):
        rate_bps("card", 6)


def test_assinatura_rejeita_parcela_maior_que_1_e_6x() -> None:
    validate_installments("subscription", "pix", 1)
    validate_installments("subscription", "card", 1)
    with pytest.raises(CatalogV2InvalidPayment, match="assinatura"):
        validate_installments("subscription", "card", 3)
    with pytest.raises(CatalogV2InvalidPayment, match="6x"):
        validate_installments("subscription", "card", 6)


def test_passe_aceita_1x_e_3x_e_recusa_0_4_e_6x() -> None:
    validate_installments("season_pass", "pix", 1)
    validate_installments("season_pass", "card", 1)
    validate_installments("season_pass", "card", 3)
    for installments in (0, 2, 4, 6):
        with pytest.raises(CatalogV2InvalidPayment):
            validate_installments("season_pass", "card", installments)
    with pytest.raises(CatalogV2InvalidPayment, match="Pix"):
        validate_installments("season_pass", "pix", 3)


def test_nenhum_produto_aceita_6x() -> None:
    for kind in ("subscription", "season_pass"):
        with pytest.raises(CatalogV2InvalidPayment, match="6x"):
            validate_installments(kind, "card", 6)


def test_split_da_ultima_parcela_e_do_passe() -> None:
    assert split_installments(4_699, 1) == [4_699]
    assert split_installments(4_699, 3) == [1_566, 1_566, 1_567]
    assert sum(split_installments(10_001, 3)) == 10_001
    with pytest.raises(CatalogV2InvalidPayment):
        split_installments(100, 6)
