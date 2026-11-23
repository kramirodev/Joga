"""Migração do CPF único: backfill, índice parcial e duplicata bloqueada (ADR 0065)."""

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

from app.core.config import get_settings
from app.modules.profile.cpf import encrypt_cpf, hash_cpf
from tests.compliance_helpers import TEST_CPF

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "cpf_hash_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "6f1a2b3c4d5e"

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


def _insert_user_with_cpf(connection: Connection, user_id: uuid.UUID, cpf: str) -> None:
    ciphertext, key_id, last2 = encrypt_cpf(cpf, user_id, get_settings())
    connection.execute(
        text("INSERT INTO users (id, status) VALUES (:id, 'active')"),
        {"id": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO user_profiles "
            "(user_id, cpf_ciphertext, cpf_key_id, cpf_last2, cpf_updated_at) "
            "VALUES (:user_id, :ciphertext, :key_id, :last2, now())"
        ),
        {
            "user_id": user_id,
            "ciphertext": ciphertext,
            "key_id": key_id,
            "last2": last2,
        },
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


def test_backfill_upgrade_downgrade_and_upgrade(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, PREVIOUS_REVISION)
    connection.commit()

    user_id = uuid.uuid4()
    _insert_user_with_cpf(connection, user_id, TEST_CPF)
    connection.commit()

    command.upgrade(config, "head")
    connection.commit()

    expected = hash_cpf(TEST_CPF, get_settings())
    stored = connection.scalar(
        text("SELECT cpf_hash FROM user_profiles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    assert stored == expected

    index_def = connection.scalar(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = :schema AND indexname = 'uq_user_profiles_cpf_hash'"
        ),
        {"schema": SCHEMA},
    )
    assert index_def is not None
    assert "UNIQUE" in index_def
    assert "cpf_hash IS NOT NULL" in index_def

    command.downgrade(config, PREVIOUS_REVISION)
    connection.commit()
    assert not _has_column(connection, "user_profiles", "cpf_hash")
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_indexes "
                "WHERE schemaname = :schema AND indexname = 'uq_user_profiles_cpf_hash'"
            ),
            {"schema": SCHEMA},
        )
        == 0
    )

    command.upgrade(config, "head")
    connection.commit()
    assert (
        connection.scalar(
            text("SELECT cpf_hash FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        == expected
    )


def test_duplicate_cpf_aborts_without_choosing_a_winner(
    alembic_env: tuple[Config, Connection],
) -> None:
    config, connection = alembic_env
    command.upgrade(config, PREVIOUS_REVISION)
    connection.commit()

    first = uuid.uuid4()
    second = uuid.uuid4()
    _insert_user_with_cpf(connection, first, TEST_CPF)
    _insert_user_with_cpf(connection, second, TEST_CPF)
    connection.commit()

    with pytest.raises(RuntimeError, match="mais de uma conta"):
        command.upgrade(config, "head")
    connection.rollback()

    assert not _has_column(connection, "user_profiles", "cpf_hash")
    assert (
        connection.scalar(
            text("SELECT count(*) FROM user_profiles WHERE cpf_ciphertext IS NOT NULL")
        )
        == 2
    )
