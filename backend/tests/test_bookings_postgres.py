"""Testes PostgreSQL de concorrência de holds (Fase 13A)."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.bookings.models import Booking, BookingTimer
from app.modules.bookings.service import BookingConflict, BookingService
from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.profile.models import Sport, SportFormat
from app.modules.venues.models import VenueAvailability, VenueSpace

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "bookings_test"
START = datetime(2026, 12, 15, 18, 0, tzinfo=UTC)
END = START + timedelta(minutes=60)

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


def test_concurrent_accepts_create_only_one_hold(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        owner = User(status="active")
        organization = Organization(name="Arena Concorrência")
        session.add_all([owner, organization])
        session.flush()
        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=owner.id,
                role=Role.OWNER.value,
            )
        )
        venue = OrganizationVenue(
            organization_id=organization.id,
            name="Arena Centro",
            timezone="UTC",
        )
        session.add(venue)
        session.flush()
        space = VenueSpace(organization_venue_id=venue.id, name="Quadra 1")
        session.add(space)
        session.flush()
        session.add(
            VenueAvailability(
                venue_space_id=space.id,
                weekday=START.isoweekday(),
                start_time=time(17, 0),
                end_time=time(23, 0),
                price_cents=40_000,
                slot_minutes=60,
            )
        )
        sport = Sport(slug="futebol", name="Futebol")
        session.add(sport)
        session.flush()
        format_ = SportFormat(
            sport_id=sport.id,
            slug="futebol-2x2",
            name="Futebol 2x2",
            team_size=2,
            total_participants=4,
            play_minutes=50,
            break_minutes=10,
            duration_minutes=60,
            version=1,
        )
        session.add(format_)
        session.flush()

        booking_ids: list[uuid.UUID] = []
        for _index in range(2):
            lobby = Lobby(
                format_id=format_.id,
                format_version=1,
                origin="manual",
                mode="casual",
                status="scheduled",
                court_preference="PRIVATE_ONLY",
                scheduled_start_at=START,
                scheduled_end_at=END,
                duration_minutes=60,
                center_lat=-22.9,
                center_lng=-43.2,
                radius_km=10,
                algorithm_version="manual_v1",
            )
            session.add(lobby)
            session.flush()
            booking = Booking(
                lobby_id=lobby.id,
                organization_id=organization.id,
                organization_venue_id=venue.id,
                venue_space_id=space.id,
                created_by=owner.id,
                status="REQUESTED",
                starts_at=START,
                ends_at=END,
                price_cents=40_000,
                seats=4,
                policy_version="v1",
                cancellation_policy="full_refund_until_confirmed",
            )
            session.add(booking)
            session.flush()
            session.add(
                BookingTimer(
                    booking_id=booking.id,
                    timer_type="T2",
                    status="RUNNING",
                    started_at=utcnow(),
                    deadline_at=utcnow() + timedelta(minutes=30),
                )
            )
            booking_ids.append(booking.id)
        session.commit()
        owner_id = owner.id

    barrier = threading.Barrier(2)

    def attempt(booking_id: uuid.UUID) -> str:
        with session_factory() as session:
            service = BookingService(session)
            barrier.wait()
            try:
                service.accept(owner_id, booking_id)
                session.commit()
                return "accepted"
            except BookingConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, booking_ids))

    assert sorted(results) == ["accepted", "conflict"]
