"""Migração do catálogo visual/esportes: upgrade, downgrade e check.

Requer `JOGA_TEST_DATABASE_URL` apontando para um PostgreSQL descartável com
PostGIS. Usa um schema isolado para não tocar nas tabelas do desenvolvedor.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "catalog_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]

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


def test_catalog_migration_upgrade_downgrade_and_check(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, "head")
    connection.commit()

    sport_columns = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = 'sports'"
            ),
            {"schema": SCHEMA},
        )
    }
    assert {"icon_key", "sort_order"} <= sport_columns
    visual_tables = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema "
                "AND table_name IN ('visual_catalog_items', "
                "'user_visual_identity', 'user_visual_unlocks')"
            ),
            {"schema": SCHEMA},
        )
    }
    assert {
        "visual_catalog_items",
        "user_visual_identity",
        "user_visual_unlocks",
    } <= visual_tables

    futevolei = connection.scalar(
        text("SELECT count(*) FROM sports WHERE slug = 'futevolei' AND active = false")
    )
    assert futevolei == 1
    platform_org = connection.scalar(
        text("SELECT count(*) FROM organizations WHERE slug = 'joga-publico'")
    )
    assert platform_org == 1
    public_flag = connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'organization_venues' "
            "AND column_name = 'is_public'"
        ),
        {"schema": SCHEMA},
    )
    assert public_flag == 1

    command.check(config)
    connection.commit()

    # Confirma o downgrade de uma revisão a partir do head público.
    command.downgrade(config, "-1")
    connection.commit()
    platform_slug = connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'organizations' "
            "AND column_name = 'slug'"
        ),
        {"schema": SCHEMA},
    )
    assert platform_slug == 0
    command.upgrade(config, "head")
    connection.commit()

    command.downgrade(config, "y8b9c0d1e2f3")
    connection.commit()
    remaining = connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'visual_catalog_items'"
        ),
        {"schema": SCHEMA},
    )
    assert remaining == 0

    command.upgrade(config, "head")
    connection.commit()
    command.check(config)
    connection.commit()
