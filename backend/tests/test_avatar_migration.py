"""Migração da tabela de avatar: upgrade, downgrade e check (Onda 1.7)."""

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
SCHEMA = "avatar_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "c8d9e0f1a2b3"
HEAD_REVISION = "d4a7b2c9e1f0"

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


def _columns(connection: Connection) -> dict[str, tuple[str, str]]:
    rows = connection.execute(
        text(
            "SELECT column_name, is_nullable, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'user_avatars'"
        ),
        {"schema": SCHEMA},
    )
    return {row[0]: (row[1], row[2]) for row in rows}


def _constraints(connection: Connection) -> set[str]:
    rows = connection.execute(
        text("SELECT conname FROM pg_constraint WHERE conrelid = to_regclass('user_avatars')")
    )
    return {row[0] for row in rows}


def test_avatar_migration_upgrade_downgrade_and_check(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env

    command.upgrade(config, "head")
    connection.commit()
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION

    columns = _columns(connection)
    assert {
        "user_id",
        "source",
        "source_url",
        "storage_key",
        "content_type",
        "size_bytes",
        "width",
        "height",
        "imported_at",
        "updated_at",
    } <= set(columns)
    assert columns["user_id"][0] == "NO"
    assert columns["source"][0] == "NO"
    assert columns["updated_at"][0] == "NO"

    constraints = _constraints(connection)
    assert {
        "pk_user_avatars",
        "fk_user_avatars_user_id_users",
        "ck_user_avatars_source_valid",
        "ck_user_avatars_instagram_scrape_complete",
        "ck_user_avatars_storage_fields_complete",
        "ck_user_avatars_size_non_negative",
        "ck_user_avatars_width_positive",
        "ck_user_avatars_height_positive",
    } <= constraints

    command.check(config)
    connection.commit()

    command.downgrade(config, PREVIOUS_REVISION)
    connection.commit()
    versions = {
        row[0] for row in connection.execute(text("SELECT version_num FROM alembic_version"))
    }
    assert PREVIOUS_REVISION in versions
    assert HEAD_REVISION not in versions
    remaining = connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'user_avatars'"
        ),
        {"schema": SCHEMA},
    )
    assert remaining == 0

    command.upgrade(config, "head")
    connection.commit()
    assert _columns(connection)
    command.check(config)
    connection.commit()
