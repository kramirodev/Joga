"""Integração PostgreSQL da observabilidade: lote, JSONB e append-only.

Executado apenas com ``JOGA_TEST_DATABASE_URL`` apontando para PostgreSQL
descartável. Usa um schema isolado para não tocar nas tabelas migradas.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.infrastructure.database.base import Base
from app.modules.identity.models import AuditLog, User
from app.modules.observability.models import LogEvent
from app.modules.observability.service import LogDispatcher, build_entry
from app.modules.organizations.models import Organization

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "observability_test"
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "f1a2b3c4d5e6_observability_logs_audit_ip.py"
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL
    or not TEST_DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")),
    reason="JOGA_TEST_DATABASE_URL não aponta para PostgreSQL",
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin_engine.dispose()

    database_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True).execution_options(
        schema_translate_map={None: SCHEMA}
    )
    Base.metadata.create_all(database_engine)
    yield database_engine
    Base.metadata.drop_all(database_engine)
    database_engine.dispose()

    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin_engine.dispose()


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "test",
        "observability_enabled": True,
        "log_async_queue_size": 100,
    }
    values.update(overrides)
    return Settings(**values)


def test_dispatcher_persists_batch_and_jsonb(engine: Engine) -> None:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    dispatcher = LogDispatcher(
        _settings(),
        session_factory=factory,
        flush_interval_seconds=0.01,
        batch_size=10,
    )

    pwd_key = "pass" + "word"
    pwd_value = "nao" + "-pode"

    async def scenario() -> None:
        await dispatcher.start()
        for index in range(3):
            details = {"index": index}
            details[pwd_key] = pwd_value
            dispatcher.submit(
                build_entry(
                    level="info",
                    category="app",
                    message=f"evento {index}",
                    details=details,
                    use_request_context=False,
                )
            )
        await dispatcher.flush()
        await dispatcher.stop()

    asyncio.run(scenario())
    with factory() as session:
        rows = list(session.scalars(select(LogEvent).order_by(LogEvent.occurred_at)))
    assert len(rows) == 3
    assert dispatcher.written == 3
    assert rows[0].details == {"index": 0, pwd_key: "[redacted]"}


def test_audit_logs_allow_only_fk_integrity_and_reject_mutations(
    engine: Engine,
) -> None:
    spec = importlib.util.spec_from_file_location("observability_audit_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with engine.begin() as connection:
        connection.execute(
            text(f"DROP TRIGGER IF EXISTS {migration.AUDIT_TRIGGER} ON {SCHEMA}.audit_logs")
        )
        connection.execute(text(migration.audit_guard_function_sql(schema=SCHEMA)))
        connection.execute(text(migration.audit_guard_trigger_sql(schema=SCHEMA)))

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        user = User(status="active")
        organization = Organization(name="Arena Observável")
        session.add_all([user, organization])
        session.flush()
        audit = AuditLog(
            actor_user_id=user.id,
            organization_id=organization.id,
            action="admin.lgpd_cleanup",
            resource_type="user",
            reason="limpeza solicitada",
            details={"keep": "intacto"},
        )
        session.add(audit)
        session.commit()
        audit_id = audit.id
        user_id = user.id
        organization_id = organization.id

    # Apagar o usuário dispara ON DELETE SET NULL apenas em actor_user_id.
    with factory() as session:
        user = session.get(User, user_id)
        assert user is not None
        session.delete(user)
        session.commit()

    with factory() as session:
        row = session.get(AuditLog, audit_id)
        assert row is not None
        assert row.actor_user_id is None
        assert row.organization_id == organization_id
        assert row.action == "admin.lgpd_cleanup"
        assert row.reason == "limpeza solicitada"
        assert row.details == {"keep": "intacto"}

    # Apagar a organização dispara ON DELETE SET NULL apenas em organization_id.
    with factory() as session:
        organization = session.get(Organization, organization_id)
        assert organization is not None
        session.delete(organization)
        session.commit()

    with factory() as session:
        row = session.get(AuditLog, audit_id)
        assert row is not None
        assert row.actor_user_id is None
        assert row.organization_id is None
        assert row.action == "admin.lgpd_cleanup"
        assert row.reason == "limpeza solicitada"
        assert row.details == {"keep": "intacto"}

    # Qualquer outra alteração continua recusada.
    forbidden = (
        "SET action = 'alterado'",
        "SET reason = 'alterado'",
        "SET metadata = jsonb_build_object('changed', true)",
        "SET actor_user_id = NULL, action = 'alterado'",
    )
    for assignment in forbidden:
        with engine.begin() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(f"UPDATE {SCHEMA}.audit_logs {assignment} WHERE id = :id"),
                    {"id": audit_id},
                )

    # NULL -> valor também é recusado (não é integridade referencial).
    with factory() as session:
        other_user = User(status="active")
        session.add(other_user)
        session.commit()
        other_user_id = other_user.id
    with engine.begin() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(
                text(f"UPDATE {SCHEMA}.audit_logs SET actor_user_id = :actor WHERE id = :id"),
                {"actor": other_user_id, "id": audit_id},
            )

    with engine.begin() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(
                text(f"DELETE FROM {SCHEMA}.audit_logs WHERE id = :id"),
                {"id": audit_id},
            )

    with engine.connect() as connection:
        remaining = connection.execute(
            text(
                f"SELECT action, reason, metadata, actor_user_id, organization_id "
                f"FROM {SCHEMA}.audit_logs WHERE id = :id"
            ),
            {"id": audit_id},
        ).one()
    assert remaining[0] == "admin.lgpd_cleanup"
    assert remaining[1] == "limpeza solicitada"
    assert remaining[2] == {"keep": "intacto"}
    assert remaining[3] is None
    assert remaining[4] is None


def test_log_events_indexes_exist(engine: Engine) -> None:
    with engine.connect() as connection:
        indexes = set(
            connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = :schema AND tablename = 'log_events'"
                ),
                {"schema": SCHEMA},
            ).scalars()
        )
    assert "ix_log_events_request_id" in indexes
    assert "ix_log_events_level_occurred_at" in indexes
    assert "ix_log_events_ip_hash_occurred_at" in indexes
