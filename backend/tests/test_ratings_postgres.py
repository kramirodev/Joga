"""Testes PostgreSQL de concorrência da aplicação de rating."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.matches.models import Match
from app.modules.matchmaking import models as matchmaking_models  # noqa: F401
from app.modules.profile import models as profile_models  # noqa: F401
from app.modules.ratelimit import models as ratelimit_models  # noqa: F401
from app.modules.ratings.models import RatingAccount, RatingEvent
from app.modules.ratings.service import RatingService
from app.modules.results import models as results_models  # noqa: F401
from tests.helpers_results import END, build_match

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "ratings_test"
AT = END + timedelta(minutes=2)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de rating ignorado",
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


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def test_concurrent_workers_apply_rating_once(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, _, _, _ = build_match(session, checked_in=10, mode="ranked")
        match.state = "FINALIZED"
        match.final_result = "TEAM_1"
        match.finalized_at = END
        session.commit()
        match_id = match.id

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    applied: list[int] = []

    def apply() -> None:
        with session_factory() as session:
            try:
                barrier.wait(timeout=15)
                result = RatingService(session).apply_match(match_id, now=AT)
                session.commit()
                applied.append(result.applied)
            except BaseException as error:  # noqa: BLE001 - inspecionado no teste
                session.rollback()
                errors.append(error)

    threads = [threading.Thread(target=apply) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(applied) == [0, 10]

    with session_factory() as session:
        match_row = session.get(Match, match_id)
        events = session.scalar(
            select(func.count()).select_from(RatingEvent).where(RatingEvent.match_id == match_id)
        )
        accounts = session.scalar(select(func.count()).select_from(RatingAccount))

    assert match_row is not None and match_row.state == "FINALIZED"
    assert events == 10
    assert accounts == 10
