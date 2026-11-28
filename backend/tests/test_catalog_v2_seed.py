"""Seed, preço resolvido no servidor e constraints do catálogo v2."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.catalog_v2.errors import (
    CatalogV2InvalidPayment,
    CatalogV2ProductNotFound,
)
from app.modules.catalog_v2.models import (
    CatalogV2Price,
    CatalogV2Product,
    CatalogV2ProductEntitlement,
    CatalogV2SeasonPass,
    CatalogV2Subscription,
)
from app.modules.catalog_v2.seed import (
    DEFAULT_PRODUCTS,
    get_active_product,
    product_id,
    seed_catalog_v2,
)
from app.modules.catalog_v2.service import price_snapshot, quote_for_product
from app.modules.passes.models import PassPlan
from app.modules.passes.plans import DEFAULT_PASS_PLANS
from app.modules.tickets.models import TicketPack
from tests.helpers_results import make_user

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)


def test_flag_nasce_desligada() -> None:
    assert Settings.model_fields["catalog_v2_enabled"].default is False


def test_seed_cria_tres_mensais_e_um_passe(db_session: Session) -> None:
    seed_catalog_v2(db_session)

    products = list(db_session.scalars(select(CatalogV2Product)).all())
    assert len(products) == 4
    subscriptions = [item for item in products if item.kind == "subscription"]
    passes = [item for item in products if item.kind == "season_pass"]
    assert [item.tickets_per_month for item in subscriptions] == [20, 40, 70]
    assert {item.months for item in subscriptions} == {1}
    assert len(passes) == 1
    assert passes[0].code == "passe_temporada"
    assert passes[0].months == 3
    assert passes[0].tickets_included == 6
    assert all(item.catalog_version == 2 for item in products)
    assert all(item.active for item in products)


def test_seed_precos_da_tabela_e_sem_6x(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    rows = {
        (price.product_id, price.payment_method, price.installments): price.amount_cents
        for price in db_session.scalars(select(CatalogV2Price)).all()
    }
    assert len(rows) == 9
    assert {installments for _, _, installments in rows} == {1, 3}

    for code, pix, card in (
        ("assinatura_mensal_20", 6_800, 7_200),
        ("assinatura_mensal_40", 12_800, 13_560),
        ("assinatura_mensal_70", 21_700, 23_030),
    ):
        product = get_active_product(db_session, code)
        assert product is not None
        assert rows[(product.id, "pix", 1)] == pix
        assert rows[(product.id, "card", 1)] == card
        assert (product.id, "card", 3) not in rows

    product = get_active_product(db_session, "passe_temporada")
    assert product is not None
    assert rows[(product.id, "pix", 1)] == 4_250
    assert rows[(product.id, "card", 1)] == 4_497
    assert rows[(product.id, "card", 3)] == 4_699


def test_seed_entitlements_separam_assinatura_e_passe(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    subscription = get_active_product(db_session, "assinatura_mensal_20")
    season_pass = get_active_product(db_session, "passe_temporada")
    assert subscription is not None and season_pass is not None

    subscription_keys = set(
        db_session.scalars(
            select(CatalogV2ProductEntitlement.entitlement_key).where(
                CatalogV2ProductEntitlement.product_id == subscription.id
            )
        ).all()
    )
    pass_keys = set(
        db_session.scalars(
            select(CatalogV2ProductEntitlement.entitlement_key).where(
                CatalogV2ProductEntitlement.product_id == season_pass.id
            )
        ).all()
    )
    assert subscription_keys == {"tickets"}
    assert pass_keys == {
        "tickets",
        "season_track",
        "cosmetics",
        "advanced_stats",
        "private_lobby",
        "cep_search",
    }
    assert "season_track" not in subscription_keys


def test_seed_e_idempotente(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    first = (
        db_session.scalar(select(func.count()).select_from(CatalogV2Product)),
        db_session.scalar(select(func.count()).select_from(CatalogV2Price)),
        db_session.scalar(select(func.count()).select_from(CatalogV2ProductEntitlement)),
    )
    seed_catalog_v2(db_session)
    second = (
        db_session.scalar(select(func.count()).select_from(CatalogV2Product)),
        db_session.scalar(select(func.count()).select_from(CatalogV2Price)),
        db_session.scalar(select(func.count()).select_from(CatalogV2ProductEntitlement)),
    )
    assert first == second == (4, 9, 9)


def test_seed_nao_toca_no_catalogo_do_piloto(db_session: Session) -> None:
    before_plans = sorted(
        db_session.scalars(select(PassPlan.code)).all(),
    )
    before_packs = sorted(
        db_session.scalars(select(TicketPack.code)).all(),
    )
    seed_catalog_v2(db_session)
    after_plans = sorted(db_session.scalars(select(PassPlan.code)).all())
    after_packs = sorted(db_session.scalars(select(TicketPack.code)).all())
    assert before_plans == after_plans
    assert before_packs == after_packs
    assert after_plans == sorted(item.code for item in DEFAULT_PASS_PLANS)
    assert len(after_plans) == 7


def test_preco_resolvido_no_servidor_bate_com_a_tabela(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    quote = quote_for_product(
        db_session,
        product_code="assinatura_mensal_20",
        payment_method="card",
        installments=1,
    )
    assert quote.amount_cents == 7_200
    assert quote.unit_amount_cents == 360
    assert quote.rate_bps == 499
    assert quote.catalog_version == 2

    pass_3x = quote_for_product(
        db_session,
        product_code="passe_temporada",
        payment_method="card",
        installments=3,
    )
    assert pass_3x.amount_cents == 4_699
    assert pass_3x.rate_bps == 905
    assert price_snapshot(pass_3x)["installments"] == 3


def test_servidor_recusa_parcela_invalida_antes_de_buscar_preco(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    with pytest.raises(CatalogV2InvalidPayment, match="assinatura"):
        quote_for_product(
            db_session,
            product_code="assinatura_mensal_20",
            payment_method="card",
            installments=3,
        )
    with pytest.raises(CatalogV2InvalidPayment, match="6x"):
        quote_for_product(
            db_session,
            product_code="passe_temporada",
            payment_method="card",
            installments=6,
        )
    with pytest.raises(CatalogV2ProductNotFound):
        quote_for_product(
            db_session,
            product_code="plano_inexistente",
            payment_method="pix",
            installments=1,
        )


def test_cliente_nao_envia_preco(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    with pytest.raises(TypeError):
        quote_for_product(  # type: ignore[call-arg]
            db_session,
            product_code="passe_temporada",
            payment_method="pix",
            installments=1,
            amount_cents=1,
        )


def test_preco_recusa_6x_no_banco(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "passe_temporada")
    assert product is not None
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CatalogV2Price(
                    product_id=product.id,
                    payment_method="card",
                    installments=6,
                    amount_cents=4_699,
                    catalog_version=2,
                )
            )
            db_session.flush()


def test_preco_pix_recusa_parcelamento(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "passe_temporada")
    assert product is not None
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CatalogV2Price(
                    product_id=product.id,
                    payment_method="pix",
                    installments=3,
                    amount_cents=4_250,
                    catalog_version=3,
                )
            )
            db_session.flush()


def test_assinatura_recusa_3x_no_banco(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "assinatura_mensal_20")
    assert product is not None
    user_id = make_user(db_session)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CatalogV2Subscription(
                    user_id=user_id,
                    product_id=product.id,
                    plan_code=product.code,
                    tickets_per_month=20,
                    amount_cents=68_000,
                    payment_method="card",
                    installments=3,
                    catalog_version=2,
                    status="pending",
                )
            )
            db_session.flush()


def test_passe_recusa_6x_no_banco(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "passe_temporada")
    assert product is not None
    user_id = make_user(db_session)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CatalogV2SeasonPass(
                    user_id=user_id,
                    product_id=product.id,
                    amount_cents=46_990,
                    payment_method="card",
                    installments=6,
                    catalog_version=2,
                    status="pending",
                )
            )
            db_session.flush()


def test_uma_assinatura_ativa_por_jogador(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "assinatura_mensal_20")
    assert product is not None
    user_id = make_user(db_session)
    common = {
        "user_id": user_id,
        "product_id": product.id,
        "plan_code": product.code,
        "tickets_per_month": 20,
        "amount_cents": 6_800,
        "payment_method": "pix",
        "installments": 1,
        "catalog_version": 2,
        "status": "active",
        "starts_at": NOW,
        "ends_at": NOW + timedelta(days=30),
    }
    db_session.add(CatalogV2Subscription(**common))
    db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CatalogV2Subscription(
                    **{**common, "catalog_version": 2, "plan_code": "outro"},
                )
            )
            db_session.flush()


def test_um_passe_ativo_por_jogador(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    product = get_active_product(db_session, "passe_temporada")
    assert product is not None
    user_id = make_user(db_session)
    common = {
        "user_id": user_id,
        "product_id": product.id,
        "amount_cents": 4_250,
        "payment_method": "pix",
        "installments": 1,
        "catalog_version": 2,
        "status": "active",
        "starts_at": NOW,
        "ends_at": NOW + timedelta(days=90),
    }
    db_session.add(CatalogV2SeasonPass(**common))
    db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(CatalogV2SeasonPass(**common))
            db_session.flush()


def test_produtos_do_piloto_permanecem_na_versao_um(db_session: Session) -> None:
    seed_catalog_v2(db_session)
    versions = set(db_session.scalars(select(PassPlan.catalog_version)).all())
    assert versions == {1}
    assert not any(
        item.code.startswith("assinatura_") for item in db_session.scalars(select(PassPlan)).all()
    )


def test_ids_de_produto_sao_estaveis() -> None:
    assert product_id("passe_temporada") == product_id("passe_temporada")
    assert product_id("passe_temporada") != product_id("assinatura_mensal_20")
    assert len({product_id(item.code) for item in DEFAULT_PRODUCTS}) == 4
