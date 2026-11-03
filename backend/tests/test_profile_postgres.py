"""Testes de descoberta geoespacial em PostgreSQL/PostGIS real."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.profile.cep import CepLocation
from app.modules.profile.models import UserRegion, Venue
from app.modules.profile.service import ProfileService

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "profile_test"


class UnusedCepResolver:
    def resolve(self, cep: str) -> CepLocation:  # pragma: no cover - não é chamado
        raise AssertionError("resolver não deveria ser chamado")


pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste PostGIS ignorado",
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


def test_postgis_discovery_uses_radius_and_orders_by_distance(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(
            UserRegion(
                user_id=user.id,
                source="cep",
                cep="01001000",
                city="São Paulo",
                state="SP",
                radius_km=10,
                center_lat=-23.5504,
                center_lng=-46.6331,
                updated_at=datetime.now(UTC),
            )
        )
        session.add_all(
            [
                Venue(
                    name="Perto",
                    kind="public",
                    city="São Paulo",
                    state="SP",
                    lat=-23.551,
                    lng=-46.634,
                ),
                Venue(
                    name="Médio",
                    kind="public",
                    city="São Paulo",
                    state="SP",
                    lat=-23.7,
                    lng=-46.8,
                ),
                Venue(
                    name="Longe",
                    kind="public",
                    city="Rio de Janeiro",
                    state="RJ",
                    lat=-22.9,
                    lng=-43.2,
                ),
            ]
        )
        session.flush()
        service = ProfileService(
            session,
            UnusedCepResolver(),
            max_radius_km=100,
            default_radius_km=10,
            max_page_size=20,
        )

        near = service.discover_venues(user.id, page=1, page_size=20)
        assert near.total == 1
        assert [item.name for item in near.items] == ["Perto"]

        region = session.get(UserRegion, user.id)
        assert region is not None
        region.radius_km = 100
        session.flush()

        wider = service.discover_venues(user.id, page=1, page_size=20)
        assert wider.total == 2
        assert [item.name for item in wider.items] == ["Perto", "Médio"]

        first_page = service.discover_venues(user.id, page=1, page_size=1)
        second_page = service.discover_venues(user.id, page=2, page_size=1)
        assert [item.name for item in first_page.items] == ["Perto"]
        assert [item.name for item in second_page.items] == ["Médio"]
