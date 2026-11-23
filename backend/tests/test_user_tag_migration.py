"""Migração da tag pública: backfill, unicidade e nome canônico.

Requer ``JOGA_TEST_DATABASE_URL`` apontando para um PostgreSQL descartável.
Usa um schema isolado para não tocar nas tabelas do desenvolvedor.
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
SCHEMA = "user_tag_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "9d3e4f5a6b7c"

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


def _insert_user(
    connection: Connection,
    user_id: uuid.UUID,
    display_name: str | None,
    *,
    created_at: str,
    with_profile: bool = True,
) -> None:
    connection.execute(
        text("INSERT INTO users (id, status, created_at) VALUES (:id, 'active', :created_at)"),
        {"id": user_id, "created_at": created_at},
    )
    if with_profile:
        connection.execute(
            text(
                "INSERT INTO user_profiles (user_id, display_name) VALUES (:user_id, :display_name)"
            ),
            {"user_id": user_id, "display_name": display_name},
        )


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


def _tags(connection: Connection) -> dict[uuid.UUID, str]:
    return {
        uuid.UUID(str(row[0])): str(row[1])
        for row in connection.execute(text("SELECT id, tag FROM users"))
    }


def _names(connection: Connection) -> dict[uuid.UUID, str | None]:
    return {
        uuid.UUID(str(row[0])): row[1]
        for row in connection.execute(text("SELECT user_id, display_name FROM user_profiles"))
    }


def test_tag_and_name_backfill_upgrade_downgrade_and_upgrade(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, PREVIOUS_REVISION)
    connection.commit()

    first = uuid.UUID("aaaaaaaa-1000-4000-8000-000000000001")
    second = uuid.UUID("aaaaaaaa-2000-4000-8000-000000000002")
    third = uuid.UUID("bbbbbbbb-1000-4000-8000-000000000003")
    fourth = uuid.UUID("cccccccc-1000-4000-8000-000000000004")
    _insert_user(connection, first, "  joão   da  silva  ", created_at="2026-01-01 00:00:00+00")
    _insert_user(connection, second, "ANA", created_at="2026-01-02 00:00:00+00")
    _insert_user(connection, third, None, created_at="2026-01-03 00:00:00+00", with_profile=False)
    _insert_user(connection, fourth, "   ", created_at="2026-01-04 00:00:00+00")
    connection.commit()

    command.upgrade(config, "head")
    connection.commit()

    assert _tags(connection) == {
        first: "#AAAAAAAA",
        second: "#AAAAAAAA20",
        third: "#BBBBBBBB",
        fourth: "#CCCCCCCC",
    }
    assert _names(connection) == {
        first: "JOÃO DA SILVA",
        second: "ANA",
        fourth: None,
    }
    nullable = connection.scalar(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'users' AND column_name = 'tag'"
        ),
        {"schema": SCHEMA},
    )
    assert nullable == "NO"
    index_def = connection.scalar(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = :schema AND indexname = 'uq_users_tag'"
        ),
        {"schema": SCHEMA},
    )
    assert index_def is not None
    assert "UNIQUE" in index_def
    command.check(config)
    connection.commit()

    command.downgrade(config, PREVIOUS_REVISION)
    connection.commit()
    assert not _has_column(connection, "users", "tag")
    # O downgrade não devolve a caixa original; o nome permanece canônico.
    assert _names(connection)[first] == "JOÃO DA SILVA"

    command.upgrade(config, "head")
    connection.commit()
    assert _tags(connection) == {
        first: "#AAAAAAAA",
        second: "#AAAAAAAA20",
        third: "#BBBBBBBB",
        fourth: "#CCCCCCCC",
    }
    assert _names(connection)[second] == "ANA"
    command.check(config)
    connection.commit()
