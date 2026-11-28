"""Migração do catálogo de assinatura e backfill do passe legado.

Requer `JOGA_TEST_DATABASE_URL` (PostgreSQL descartável). Usa schema isolado.
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
SCHEMA = "pass_subscription_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "z9c0d1e2f3a4"

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


def _insert_legacy_pass(connection: Connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    delivery_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO users (id, status) VALUES (:id, 'active')"),
        {"id": user_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO pass_subscriptions (
                id, user_id, plan_code, tickets_per_month, amount_cents, status,
                starts_at, ends_at, paid_at
            ) VALUES (
                :id, :user_id, 'craque', 20, 19500, 'active',
                now() - interval '40 days', now() + interval '50 days', now() - interval '40 days'
            )
            """
        ),
        {"id": subscription_id, "user_id": user_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO pass_deliveries (
                id, subscription_id, month_index, tickets, delivered_at
            ) VALUES (
                :id, :subscription_id, 1, 20, now() - interval '40 days'
            )
            """
        ),
        {"id": delivery_id, "subscription_id": subscription_id},
    )
    connection.commit()
    return subscription_id


def test_upgrade_backfills_legacy_and_downgrade_is_reversible(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, PREVIOUS_REVISION)
    connection.commit()

    subscription_id = _insert_legacy_pass(connection)

    command.upgrade(config, "head")
    connection.commit()

    plans = connection.execute(
        text(
            "SELECT code, months, unit_price_cents, cycle_amount_cents, active "
            "FROM pass_plans ORDER BY months, tickets_per_month"
        )
    ).all()
    assert len(plans) == 7
    assert str(plans[0].code) == "mensal_20"
    assert int(plans[-1].cycle_amount_cents) == 72_000

    subscription = connection.execute(
        text(
            "SELECT cycle_months, unit_price_cents, installments, refund_window_ends_at "
            "FROM pass_subscriptions WHERE id = :id"
        ),
        {"id": subscription_id},
    ).one()
    assert int(subscription.cycle_months) == 3
    assert int(subscription.unit_price_cents) == 325
    assert int(subscription.installments) == 1
    assert subscription.refund_window_ends_at is not None

    delivery = connection.execute(
        text(
            "SELECT period, starts_at, ends_at, status, closed_at "
            "FROM pass_deliveries WHERE subscription_id = :id"
        ),
        {"id": subscription_id},
    ).one()
    assert str(delivery.period) == delivery.starts_at.strftime("%Y-%m")
    assert delivery.ends_at > delivery.starts_at
    assert str(delivery.status) == "closed"
    assert delivery.closed_at is not None

    inactive_packs = connection.scalar(
        text("SELECT count(*) FROM ticket_packs WHERE active = true")
    )
    assert inactive_packs == 0

    command.downgrade(config, PREVIOUS_REVISION)
    connection.commit()
    columns = {
        row.column_name
        for row in connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = 'pass_subscriptions'"
            ),
            {"schema": SCHEMA},
        )
    }
    assert "cycle_months" not in columns
    assert "unit_price_cents" not in columns
    tables = {
        row.table_name
        for row in connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = 'pass_plans'"
            ),
            {"schema": SCHEMA},
        )
    }
    assert tables == set()
    restored_packs = connection.scalar(
        text("SELECT count(*) FROM ticket_packs WHERE active = true")
    )
    assert restored_packs == 4

    command.upgrade(config, "head")
    connection.commit()
    command.check(config)
    connection.commit()
