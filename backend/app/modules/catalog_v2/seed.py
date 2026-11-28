"""Seed idempotente do catálogo v2 (ADR 0079 §1 e §4).

Não altera ``pass_plans``, ``pass_subscriptions``, ``pass_deliveries`` nem os
pacotes do piloto. Rodar de novo não sobrescreve preço existente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog_v2.models import (
    CATALOG_V2_VERSION,
    CatalogV2Price,
    CatalogV2Product,
    CatalogV2ProductEntitlement,
)
from app.modules.catalog_v2.pricing import (
    PIX_PRICE_CENTS,
    SEASON_PASS_CARD_1X_CENTS,
    SEASON_PASS_CARD_3X_CENTS,
    SUBSCRIPTION_UNIT_PRICES_CENTS,
    quote_subscription,
)

CATALOG_NAMESPACE = uuid.UUID("a6d5f1e2-7b3c-4f8a-9d10-5e6f7a8b9c0d")


@dataclass(frozen=True)
class ProductDefinition:
    code: str
    kind: str
    label: str
    months: int
    tickets_per_month: int | None
    tickets_included: int | None
    entitlements: tuple[str, ...]


def product_id(code: str) -> uuid.UUID:
    return uuid.uuid5(CATALOG_NAMESPACE, f"product:{code}")


DEFAULT_PRODUCTS: tuple[ProductDefinition, ...] = (
    ProductDefinition(
        code="assinatura_mensal_20",
        kind="subscription",
        label="Assinatura mensal 20",
        months=1,
        tickets_per_month=20,
        tickets_included=None,
        entitlements=("tickets",),
    ),
    ProductDefinition(
        code="assinatura_mensal_40",
        kind="subscription",
        label="Assinatura mensal 40",
        months=1,
        tickets_per_month=40,
        tickets_included=None,
        entitlements=("tickets",),
    ),
    ProductDefinition(
        code="assinatura_mensal_70",
        kind="subscription",
        label="Assinatura mensal 70",
        months=1,
        tickets_per_month=70,
        tickets_included=None,
        entitlements=("tickets",),
    ),
    ProductDefinition(
        code="passe_temporada",
        kind="season_pass",
        label="Passe de temporada",
        months=3,
        tickets_per_month=None,
        tickets_included=6,
        entitlements=(
            "tickets",
            "season_track",
            "cosmetics",
            "advanced_stats",
            "private_lobby",
            "cep_search",
        ),
    ),
)

PASS_CODE = "passe_temporada"


def default_price_rows() -> list[tuple[str, str, int, int]]:
    """(product_code, método, parcelas, centavos) da tabela aprovada."""

    rows: list[tuple[str, str, int, int]] = []
    for unit_price, tickets, code in zip(
        SUBSCRIPTION_UNIT_PRICES_CENTS,
        (20, 40, 70),
        ("assinatura_mensal_20", "assinatura_mensal_40", "assinatura_mensal_70"),
        strict=True,
    ):
        pix_total = unit_price * tickets
        card = quote_subscription(
            product_code=code,
            unit_pix_cents=unit_price,
            tickets_per_month=tickets,
            payment_method="card",
            installments=1,
            catalog_version=CATALOG_V2_VERSION,
        )
        rows.append((code, "pix", 1, pix_total))
        rows.append((code, "card", 1, card.amount_cents))
    rows.extend(
        [
            (PASS_CODE, "pix", 1, PIX_PRICE_CENTS),
            (PASS_CODE, "card", 1, SEASON_PASS_CARD_1X_CENTS),
            (PASS_CODE, "card", 3, SEASON_PASS_CARD_3X_CENTS),
        ]
    )
    return rows


def seed_catalog_v2(
    session: Session,
    *,
    catalog_version: int = CATALOG_V2_VERSION,
) -> None:
    """Cria produtos, entitlements e preços ausentes; nunca sobrescreve."""

    products = {product.code: product for product in session.scalars(select(CatalogV2Product))}
    for definition in DEFAULT_PRODUCTS:
        product = products.get(definition.code)
        if product is None:
            product = CatalogV2Product(
                id=product_id(definition.code),
                code=definition.code,
                kind=definition.kind,
                label=definition.label,
                months=definition.months,
                tickets_per_month=definition.tickets_per_month,
                tickets_included=definition.tickets_included,
                catalog_version=catalog_version,
                active=True,
            )
            session.add(product)
            products[definition.code] = product
    session.flush()

    existing_entitlements = {
        (row.product_id, row.entitlement_key)
        for row in session.scalars(select(CatalogV2ProductEntitlement))
    }
    for definition in DEFAULT_PRODUCTS:
        product = products[definition.code]
        for key in definition.entitlements:
            if (product.id, key) in existing_entitlements:
                continue
            session.add(
                CatalogV2ProductEntitlement(
                    product_id=product.id,
                    entitlement_key=key,
                )
            )

    existing_prices = {
        (row.product_id, row.payment_method, row.installments, row.catalog_version)
        for row in session.scalars(select(CatalogV2Price))
    }
    for code, method, installments, amount_cents in default_price_rows():
        product = products[code]
        price_key = (product.id, method, installments, catalog_version)
        if price_key in existing_prices:
            continue
        session.add(
            CatalogV2Price(
                product_id=product.id,
                payment_method=method,
                installments=installments,
                amount_cents=amount_cents,
                catalog_version=catalog_version,
            )
        )
    session.flush()


def list_active_products(session: Session) -> list[CatalogV2Product]:
    return list(
        session.scalars(
            select(CatalogV2Product)
            .where(CatalogV2Product.active.is_(True))
            .order_by(CatalogV2Product.kind.asc(), CatalogV2Product.months.asc())
        ).all()
    )


def get_active_product(session: Session, code: str) -> CatalogV2Product | None:
    return session.scalars(
        select(CatalogV2Product).where(
            CatalogV2Product.code == code,
            CatalogV2Product.active.is_(True),
        )
    ).first()


def get_price(
    session: Session,
    product: CatalogV2Product,
    *,
    payment_method: str,
    installments: int,
    catalog_version: int | None = None,
) -> CatalogV2Price | None:
    version = catalog_version or product.catalog_version
    return session.scalars(
        select(CatalogV2Price).where(
            CatalogV2Price.product_id == product.id,
            CatalogV2Price.payment_method == payment_method,
            CatalogV2Price.installments == installments,
            CatalogV2Price.catalog_version == version,
        )
    ).first()
