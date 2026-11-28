"""Reembolso proporcional ao não usado, puro e atrás de flag (ADR 0079 §6)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.catalog_v2.errors import CatalogV2Disabled, CatalogV2InvalidPayment
from app.modules.catalog_v2.refund import (
    season_pass_refund,
    subscription_no_use_refund,
    subscription_refund,
)
from app.modules.catalog_v2.service import (
    calculate_season_pass_refund,
    calculate_subscription_no_use_refund,
    calculate_subscription_refund,
)


def test_assinatura_pix_desconta_apenas_o_custo_do_meio() -> None:
    result = subscription_refund(
        unused_tickets=10,
        paid_unit_cents=340,
        payment_method="pix",
    )
    assert result.gross_cents == 3_400
    assert result.rate_bps == 99
    assert result.fee_cents == 34
    assert result.net_cents == 3_366


def test_assinatura_cartao_1x_e_sem_uso_em_7_dias() -> None:
    result = subscription_refund(
        unused_tickets=20,
        paid_unit_cents=360,
        payment_method="card",
    )
    assert result.gross_cents == 7_200
    assert result.fee_cents == 359
    assert result.net_cents == 6_841

    sem_taxa = subscription_no_use_refund(
        paid_total_cents=6_800,
        payment_method="pix",
        psp_refunded_fee=False,
    )
    assert sem_taxa.fee_cents == 67
    assert sem_taxa.net_cents == 6_733

    com_taxa = subscription_no_use_refund(
        paid_total_cents=6_800,
        payment_method="pix",
        psp_refunded_fee=True,
    )
    assert com_taxa.fee_cents == 0
    assert com_taxa.net_cents == 6_800


def test_passe_exemplo_da_adr_1_mes_usado_e_6_tickets() -> None:
    result = season_pass_refund(
        months_unused=2,
        tickets_redeemed=6,
        payment_method="pix",
    )
    assert result.gross_cents == 2_833
    assert result.fee_cents == 28
    assert result.tickets_deduction_cents == 1_500
    assert result.net_cents == 1_305


def test_passe_3x_usa_905_bps() -> None:
    result = season_pass_refund(
        months_unused=2,
        tickets_redeemed=0,
        payment_method="card",
        installments=3,
    )
    assert result.rate_bps == 905
    assert result.fee_cents == 256
    assert result.net_cents == 2_577


def test_passe_12_tickets_resgatados_zera_o_reembolso() -> None:
    result = season_pass_refund(
        months_unused=2,
        tickets_redeemed=12,
        payment_method="pix",
    )
    assert result.net_cents == 0


@pytest.mark.parametrize(
    ("months_unused", "tickets_redeemed"),
    [(0, 0), (0, 12), (1, 0), (1, 12), (3, 0), (3, 12)],
)
def test_reembolso_nunca_e_negativo(months_unused: int, tickets_redeemed: int) -> None:
    result = season_pass_refund(
        months_unused=months_unused,
        tickets_redeemed=tickets_redeemed,
        payment_method="card",
        installments=1,
    )
    assert result.net_cents >= 0


def test_casos_limite_invalidos() -> None:
    with pytest.raises(ValueError):
        season_pass_refund(
            months_unused=4,
            tickets_redeemed=0,
            payment_method="pix",
        )
    with pytest.raises(ValueError):
        season_pass_refund(
            months_unused=1,
            tickets_redeemed=-1,
            payment_method="pix",
        )
    with pytest.raises(CatalogV2InvalidPayment, match="6x"):
        season_pass_refund(
            months_unused=1,
            tickets_redeemed=0,
            payment_method="card",
            installments=6,
        )
    with pytest.raises(CatalogV2InvalidPayment, match="assinatura"):
        subscription_refund(
            unused_tickets=1,
            paid_unit_cents=340,
            payment_method="card",
            installments=3,
        )


def test_flag_desligada_bloqueia_reembolso() -> None:
    settings = Settings(catalog_v2_enabled=False)
    with pytest.raises(CatalogV2Disabled):
        calculate_subscription_refund(
            settings,
            unused_tickets=1,
            paid_unit_cents=340,
            payment_method="pix",
        )
    with pytest.raises(CatalogV2Disabled):
        calculate_subscription_no_use_refund(
            settings,
            paid_total_cents=6_800,
            payment_method="pix",
        )
    with pytest.raises(CatalogV2Disabled):
        calculate_season_pass_refund(
            settings,
            months_unused=2,
            tickets_redeemed=0,
            payment_method="pix",
        )


def test_flag_ligada_libera_reembolso() -> None:
    settings = Settings(catalog_v2_enabled=True)
    result = calculate_season_pass_refund(
        settings,
        months_unused=2,
        tickets_redeemed=6,
        payment_method="pix",
    )
    assert result.net_cents == 1_305

    assert (
        calculate_subscription_refund(
            settings,
            unused_tickets=10,
            paid_unit_cents=340,
            payment_method="pix",
        ).net_cents
        == 3_366
    )
