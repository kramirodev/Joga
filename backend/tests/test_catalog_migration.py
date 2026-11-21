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
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "catalog_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "4c5d6e7f8a9b"
PRE_REPAIR_REVISION = "b1c2d3e4f5a6"
LEGACY_REVISION = "a0b1c2d3e4f5"

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

    # Confirma o downgrade da revisão b1 a partir do head público.
    command.downgrade(config, LEGACY_REVISION)
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


def _drop_z9_objects(connection: Connection) -> None:
    """Simula um banco que avançou de a0b1 sem ter aplicado z9."""

    statements = (
        "DROP TABLE IF EXISTS user_visual_unlocks CASCADE",
        "DROP TABLE IF EXISTS user_visual_identity CASCADE",
        "DROP TABLE IF EXISTS visual_catalog_items CASCADE",
        "DELETE FROM sport_formats WHERE slug = 'futevolei-3x3'",
        "DELETE FROM sports WHERE slug = 'futevolei'",
        "ALTER TABLE sport_formats DROP CONSTRAINT IF EXISTS ck_sport_formats_score_model_valid",
        "ALTER TABLE sport_formats DROP CONSTRAINT IF EXISTS "
        "ck_sport_formats_period_count_positive",
        "ALTER TABLE sport_formats DROP CONSTRAINT IF EXISTS "
        "ck_sport_formats_players_per_team_positive",
        "ALTER TABLE sport_formats DROP COLUMN IF EXISTS positions",
        "ALTER TABLE sport_formats DROP COLUMN IF EXISTS score_model",
        "ALTER TABLE sport_formats DROP COLUMN IF EXISTS period_count",
        "ALTER TABLE sport_formats DROP COLUMN IF EXISTS players_per_team",
        "ALTER TABLE sports DROP CONSTRAINT IF EXISTS ck_sports_sort_order_non_negative",
        "ALTER TABLE sports DROP COLUMN IF EXISTS sort_order",
        "ALTER TABLE sports DROP COLUMN IF EXISTS icon_key",
    )
    for statement in statements:
        connection.execute(text(statement))


def _has_table(connection: Connection, table_name: str) -> bool:
    return (
        connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :table_name"
            ),
            {"schema": SCHEMA, "table_name": table_name},
        )
        or 0
    ) == 1


def _has_column(connection: Connection, table_name: str, column_name: str) -> bool:
    return (
        connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table_name "
                "AND column_name = :column_name"
            ),
            {"schema": SCHEMA, "table_name": table_name, "column_name": column_name},
        )
        or 0
    ) == 1


def _has_constraint(connection: Connection, table_name: str, constraint_name: str) -> bool:
    return (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE conrelid = to_regclass(:table_name) AND conname = :constraint_name"
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        )
        or 0
    ) == 1


def _has_index(connection: Connection, index_name: str) -> bool:
    return (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_indexes "
                "WHERE schemaname = current_schema() AND indexname = :index_name"
            ),
            {"index_name": index_name},
        )
        or 0
    ) == 1


def _assert_catalog_endpoints_ok() -> None:
    assert TEST_DATABASE_URL is not None
    api_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"options": f"-csearch_path={SCHEMA},public,extensions"},
    )
    app = create_app()

    def override_session() -> Iterator[Session]:
        with Session(api_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            for path in (
                "/api/v1/catalog/sports",
                "/api/v1/catalog/visual",
                "/api/v1/sports",
            ):
                response = client.get(path)
                assert response.status_code == 200, f"{path}: {response.text}"
    finally:
        api_engine.dispose()


def test_repair_migration_heals_legacy_database(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env

    # Estado antigo: z9 foi aplicada, a0b1 entrou depois, e o boot seguinte
    # aplicou b1 sem reexecutar z9.
    command.upgrade(config, "z9c0d1e2f3a4")
    command.upgrade(config, LEGACY_REVISION)
    connection.commit()
    _drop_z9_objects(connection)
    connection.commit()
    command.upgrade(config, PRE_REPAIR_REVISION)
    connection.commit()

    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
        PRE_REPAIR_REVISION
    )
    assert not _has_table(connection, "visual_catalog_items")
    assert not _has_column(connection, "sports", "icon_key")
    assert not _has_column(connection, "sport_formats", "players_per_team")

    command.upgrade(config, "head")
    connection.commit()

    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
    assert _has_table(connection, "visual_catalog_items")
    assert _has_table(connection, "user_visual_identity")
    assert _has_table(connection, "user_visual_unlocks")
    assert _has_column(connection, "sports", "icon_key")
    assert _has_column(connection, "sports", "sort_order")
    assert _has_column(connection, "sport_formats", "players_per_team")
    assert _has_column(connection, "sport_formats", "period_count")
    assert _has_column(connection, "sport_formats", "score_model")
    assert _has_column(connection, "sport_formats", "positions")
    assert _has_constraint(connection, "sports", "ck_sports_sort_order_non_negative")
    assert _has_constraint(
        connection, "sport_formats", "ck_sport_formats_players_per_team_positive"
    )
    assert _has_constraint(connection, "sport_formats", "ck_sport_formats_period_count_positive")
    assert _has_constraint(connection, "sport_formats", "ck_sport_formats_score_model_valid")
    assert _has_constraint(
        connection,
        "visual_catalog_items",
        "ck_visual_catalog_items_ck_visual_catalog_items_kind_valid",
    )
    assert _has_constraint(
        connection,
        "visual_catalog_items",
        "ck_visual_catalog_items_ck_visual_catalog_items_unlock__8f86",
    )
    assert _has_index(connection, "ix_visual_catalog_items_kind_active")
    assert _has_index(connection, "ix_user_visual_unlocks_user")

    visual_items = connection.scalar(text("SELECT count(*) FROM visual_catalog_items"))
    assert visual_items == 14
    futevolei = connection.scalar(
        text("SELECT count(*) FROM sports WHERE slug = 'futevolei' AND active = false")
    )
    assert futevolei == 1
    futevolei_format = connection.scalar(
        text(
            "SELECT count(*) FROM sport_formats "
            "WHERE slug = 'futevolei-3x3' AND players_per_team = 3 "
            "AND period_count = 1 AND score_model = 'sets_points'"
        )
    )
    assert futevolei_format == 1

    command.check(config)
    connection.commit()
    _assert_catalog_endpoints_ok()

    # O downgrade do reparo é no-op: não remove o catálogo nem as seeds.
    command.downgrade(config, PRE_REPAIR_REVISION)
    connection.commit()
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
        PRE_REPAIR_REVISION
    )
    assert connection.scalar(text("SELECT count(*) FROM visual_catalog_items")) == 14

    command.upgrade(config, "head")
    connection.commit()
    assert connection.scalar(text("SELECT count(*) FROM visual_catalog_items")) == 14

    # Repetição sobre um schema parcialmente danificado: o reparo recria cada
    # objeto e a seed ausente sem duplicar nem apagar os demais.
    command.downgrade(config, PRE_REPAIR_REVISION)
    connection.commit()
    connection.execute(text("DROP INDEX IF EXISTS ix_visual_catalog_items_kind_active"))
    connection.execute(
        text(
            "ALTER TABLE visual_catalog_items DROP CONSTRAINT IF EXISTS "
            "ck_visual_catalog_items_ck_visual_catalog_items_unlock__8f86"
        )
    )
    connection.execute(text("DELETE FROM visual_catalog_items WHERE key = 'accent-roxo'"))
    connection.execute(text("DELETE FROM sport_formats WHERE slug = 'futevolei-3x3'"))
    connection.execute(text("DELETE FROM sports WHERE slug = 'futevolei'"))
    connection.commit()

    command.upgrade(config, "head")
    connection.commit()

    assert _has_index(connection, "ix_visual_catalog_items_kind_active")
    assert _has_constraint(
        connection,
        "visual_catalog_items",
        "ck_visual_catalog_items_ck_visual_catalog_items_unlock__8f86",
    )
    assert connection.scalar(text("SELECT count(*) FROM visual_catalog_items")) == 14
    assert connection.scalar(text("SELECT count(*) FROM sports WHERE slug = 'futevolei'")) == 1
    assert (
        connection.scalar(text("SELECT count(*) FROM sport_formats WHERE slug = 'futevolei-3x3'"))
        == 1
    )
    assert (
        connection.scalar(
            text("SELECT count(*) FROM visual_catalog_items WHERE key = 'accent-roxo'")
        )
        == 1
    )
    command.check(config)
    connection.commit()
