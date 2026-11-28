"""Migração do catálogo v2: aditiva, com seed e reversível (ADR 0079).

Requer ``JOGA_TEST_DATABASE_URL`` (PostgreSQL descartável) e usa schema isolado.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "catalog_v2_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "bc23de45fa67"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de migração ignorado",
)


@pytest.fixture
def alembic_env() -> Iterator[tuple[Config, Connection]]:
    assert TEST_DATABASE_URL is not None
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    connection = engine.connect()
    connection.execute(text(f"SET search_path TO {SCHEMA}, public, extensions"))
    connection.commit()

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.attributes["connection"] = connection
    config.attributes["version_table_schema"] = SCHEMA
    try:
        yield config, connection
    finally:
        connection.close()
        engine.dispose()
        with admin_engine.begin() as admin_connection:
            admin_connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        admin_engine.dispose()


def _insert_legacy_subscription(connection: Connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO users (id, tag, status) VALUES (:id, :tag, 'active')"),
        {"id": user_id, "tag": f"#T{user_id.hex[:10].upper()}"},
    )
    connection.execute(
        text(
            """
            INSERT INTO pass_subscriptions (
                id, user_id, plan_code, tickets_per_month, amount_cents, status,
                starts_at, ends_at, paid_at, cycle_months, unit_price_cents,
                installments, refund_window_ends_at
            ) VALUES (
                :id, :user_id, 'mensal_40', 40, 12800, 'active',
                now() - interval '10 days', now() + interval '20 days',
                now() - interval '10 days', 1, 320, 1, now() + interval '7 days'
            )
            """
        ),
        {"id": subscription_id, "user_id": user_id},
    )
    connection.commit()
    return subscription_id


def _tables(connection: Connection) -> set[str]:
    return {
        str(row.table_name)
        for row in connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name LIKE 'catalog_v2_%'"
            ),
            {"schema": SCHEMA},
        )
    }


def _check_names(connection: Connection, table: str) -> set[str]:
    return {
        str(row.conname)
        for row in connection.execute(
            text(
                "SELECT c.conname FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE n.nspname = :schema AND t.relname = :table"
            ),
            {"schema": SCHEMA, "table": table},
        )
    }


def test_upgrade_is_additive_and_downgrade_is_reversible(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, PREVIOUS_REVISION)
    connection.commit()

    legacy_subscription_id = _insert_legacy_subscription(connection)
    legacy_plans = connection.scalar(text("SELECT count(*) FROM pass_plans"))
    assert legacy_plans == 7
    assert _tables(connection) == set()

    command.upgrade(config, "head")
    connection.commit()

    assert _tables(connection) == {
        "catalog_v2_products",
        "catalog_v2_product_entitlements",
        "catalog_v2_prices",
        "catalog_v2_subscriptions",
        "catalog_v2_subscription_cycles",
        "catalog_v2_season_passes",
        "catalog_v2_season_pass_deliveries",
    }

    products = connection.execute(
        text(
            "SELECT code, kind, months, tickets_per_month, tickets_included, "
            "catalog_version, active FROM catalog_v2_products ORDER BY code"
        )
    ).all()
    assert len(products) == 4
    assert [row.code for row in products] == [
        "assinatura_mensal_20",
        "assinatura_mensal_40",
        "assinatura_mensal_70",
        "passe_temporada",
    ]
    assert [row.tickets_per_month for row in products[:3]] == [20, 40, 70]
    assert all(row.kind == "subscription" for row in products[:3])
    assert products[3].kind == "season_pass"
    assert products[3].months == 3
    assert products[3].tickets_included == 6
    assert all(row.catalog_version == 2 and row.active for row in products)

    prices = connection.execute(
        text(
            "SELECT p.code, pr.payment_method, pr.installments, pr.amount_cents "
            "FROM catalog_v2_prices pr "
            "JOIN catalog_v2_products p ON p.id = pr.product_id "
            "ORDER BY p.code, pr.payment_method, pr.installments"
        )
    ).all()
    assert len(prices) == 9
    assert all(row.installments in (1, 3) for row in prices)
    assert not any(row.installments == 6 for row in prices)
    pass_prices = [
        (row.payment_method, row.installments, row.amount_cents)
        for row in prices
        if row.code == "passe_temporada"
    ]
    assert pass_prices == [("card", 1, 4_497), ("card", 3, 4_699), ("pix", 1, 4_250)]
    subscription_installments = {
        row.installments for row in prices if row.code != "passe_temporada"
    }
    assert subscription_installments == {1}

    pass_entitlements = connection.scalar(
        text(
            "SELECT count(*) FROM catalog_v2_product_entitlements e "
            "JOIN catalog_v2_products p ON p.id = e.product_id "
            "WHERE p.code = 'passe_temporada'"
        )
    )
    assert pass_entitlements == 6
    subscription_keys = {
        str(row.entitlement_key)
        for row in connection.execute(
            text(
                "SELECT e.entitlement_key FROM catalog_v2_product_entitlements e "
                "JOIN catalog_v2_products p ON p.id = e.product_id "
                "WHERE p.code = 'assinatura_mensal_20'"
            )
        )
    }
    assert subscription_keys == {"tickets"}

    assert "ck_catalog_v2_prices_installments_valid" in _check_names(
        connection, "catalog_v2_prices"
    )
    assert "ck_catalog_v2_prices_pix_single_installment" in _check_names(
        connection, "catalog_v2_prices"
    )
    assert "ck_catalog_v2_subscriptions_subscription_single_installment" in _check_names(
        connection, "catalog_v2_subscriptions"
    )

    # O legado e o piloto continuam intactos e sem expiração.
    assert connection.scalar(text("SELECT count(*) FROM pass_plans")) == 7
    assert connection.scalar(text("SELECT count(*) FROM ticket_packs WHERE active")) == 0
    legacy = connection.execute(
        text(
            "SELECT plan_code, amount_cents, cycle_months, unit_price_cents, installments "
            "FROM pass_subscriptions WHERE id = :id"
        ),
        {"id": legacy_subscription_id},
    ).one()
    assert legacy.plan_code == "mensal_40"
    assert int(legacy.amount_cents) == 12_800
    assert int(legacy.cycle_months) == 1
    assert int(legacy.unit_price_cents) == 320
    assert int(legacy.installments) == 1

    command.downgrade(config, PREVIOUS_REVISION)
    connection.commit()

    assert _tables(connection) == set()
    assert connection.scalar(text("SELECT count(*) FROM pass_plans")) == 7
    assert connection.scalar(text("SELECT count(*) FROM ticket_packs WHERE active")) == 0
    assert (
        connection.scalar(
            text("SELECT count(*) FROM pass_subscriptions WHERE id = :id"),
            {"id": legacy_subscription_id},
        )
        == 1
    )

    command.upgrade(config, "head")
    connection.commit()
    command.check(config)
    connection.commit()
