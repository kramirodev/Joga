"""Testes PostgreSQL de constraints e concorrência de quadras (Fase 12A)."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.permissions import Role
from app.modules.venues.models import VenueAvailability, VenueSpace
from app.modules.venues.service import VenueConflict, VenueService
from app.modules.venues.storage import LocalPhotoStorage

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "venues_test"

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
def tenant(session_factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with session_factory() as session:
        user = User(status="active")
        organization = Organization(name="Arena PostgreSQL")
        session.add_all([user, organization])
        session.flush()
        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=Role.OWNER.value,
            )
        )
        from app.modules.organizations.models import OrganizationVenue

        venue = OrganizationVenue(organization_id=organization.id, name="Arena Centro")
        session.add(venue)
        session.flush()
        space = VenueSpace(organization_venue_id=venue.id, name="Quadra 1")
        session.add(space)
        session.commit()
        return user.id, organization.id, space.id


def test_space_name_is_unique_per_venue(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        user = User(status="active")
        organization = Organization(name="Arena")
        session.add_all([user, organization])
        session.flush()
        from app.modules.organizations.models import OrganizationVenue

        venue = OrganizationVenue(organization_id=organization.id, name="Centro")
        session.add(venue)
        session.flush()
        session.add(VenueSpace(organization_venue_id=venue.id, name="Quadra 1"))
        session.flush()
        session.add(VenueSpace(organization_venue_id=venue.id, name="Quadra 1"))
        with pytest.raises(IntegrityError):
            session.flush()


def test_availability_constraints_reject_invalid_windows(
    session_factory: sessionmaker[Session],
    tenant: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    _, _, space_id = tenant
    with session_factory() as session:
        session.add(
            VenueAvailability(
                venue_space_id=space_id,
                weekday=0,
                start_time=time(18, 0),
                end_time=time(22, 0),
                price_cents=10000,
                slot_minutes=60,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_concurrent_overlapping_availability_is_serialized(
    session_factory: sessionmaker[Session],
    tenant: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    user_id, organization_id, space_id = tenant
    barrier = threading.Barrier(2)

    def attempt(start: time, end: time) -> str:
        with session_factory() as session:
            service = VenueService(session, LocalPhotoStorage(tmp_path))
            barrier.wait()
            try:
                service.create_availability(
                    user_id,
                    organization_id,
                    session.get(VenueSpace, space_id).organization_venue_id,
                    space_id,
                    weekday=1,
                    start_time=start,
                    end_time=end,
                    price_cents=10000,
                    slot_minutes=60,
                )
                session.commit()
                return "created"
            except VenueConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda window: attempt(*window),
                [(time(18, 0), time(21, 0)), (time(20, 0), time(22, 0))],
            )
        )

    assert sorted(results) == ["conflict", "created"]
