"""Concorrência da compra de pacote em PostgreSQL (onda 1)."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.tickets.models import TicketPurchase
from app.modules.tickets.service import create_purchase, seed_default_packs

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "tickets_test"

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


@pytest.fixture
def user_id(session_factory: sessionmaker[Session]) -> uuid.UUID:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        seed_default_packs(session)
        session.commit()
        return user.id


def test_concurrent_purchase_returns_single_pending_order(
    session_factory: sessionmaker[Session],
    user_id: uuid.UUID,
) -> None:
    barrier = threading.Barrier(2)

    def attempt() -> uuid.UUID:
        with session_factory() as session:
            barrier.wait()
            purchase = create_purchase(session, user_id, "pequeno")
            session.commit()
            return purchase.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _index: attempt(), range(2)))

    assert len(set(ids)) == 1
    with session_factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(TicketPurchase)
            .where(
                TicketPurchase.user_id == user_id,
                TicketPurchase.status == "pending",
            )
        )
    assert count == 1
