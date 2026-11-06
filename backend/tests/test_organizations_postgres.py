"""Testes PostgreSQL de constraints e concorrência de organizações (Fase 11)."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.permissions import Role
from app.modules.organizations.service import LastOwner, OrganizationService

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "organizations_test"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de integração ignorado",
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None

    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin_engine.dispose()

    database_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    ).execution_options(schema_translate_map={None: SCHEMA})
    Base.metadata.create_all(database_engine)
    yield database_engine

    Base.metadata.drop_all(database_engine)
    database_engine.dispose()

    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def test_membership_unique_constraint_blocks_duplicate_pair(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        organization = Organization(name="Arena Única")
        session.add_all([user, organization])
        session.flush()
        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=Role.OWNER.value,
            )
        )
        session.flush()

        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=Role.ADMIN.value,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_only_one_concurrent_last_owner_demotion_wins(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        first = User(status="active")
        second = User(status="active")
        session.add_all([first, second])
        session.flush()
        service = OrganizationService(session)
        organization = service.create(first.id, "Arena Concorrente")
        service.add_member(
            first.id,
            organization.id,
            second.id,
            Role.OWNER,
        )
        session.commit()
        first_id = first.id
        second_id = second.id
        organization_id = organization.id

    barrier = threading.Barrier(2)

    def demote(user_id: uuid.UUID) -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                OrganizationService(session).change_member_role(
                    user_id,
                    organization_id,
                    user_id,
                    Role.ADMIN,
                )
                session.commit()
                return "ok"
            except LastOwner:
                session.rollback()
                return "last_owner"
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                return f"error:{exc!r}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(demote, (first_id, second_id)))

    assert sorted(results) == ["last_owner", "ok"], results

    with session_factory() as session:
        owners = session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == Role.OWNER.value,
            )
        )
        assert owners == 1
