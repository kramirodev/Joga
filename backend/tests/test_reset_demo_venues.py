"""Reset das quadras do demo preserva contas e remove o grafo de teste."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby
from app.modules.organizations.models import (
    Organization,
    OrganizationVenue,
)
from app.modules.payments.models import PaymentEvent
from app.modules.profile.models import UserProfile
from app.modules.venues.models import (
    VenueAvailability,
    VenueBlackout,
    VenueBusinessHour,
    VenuePhoto,
    VenueSpace,
)
from scripts.reset_demo_venues import main, reset_demo_venues
from tests.test_ticket_settlement import api_client, open_booking, setup_context


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_reset_removes_only_demo_venue_graph_and_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    booking = open_booking(api, context)
    booking_id = uuid.UUID(booking["id"])
    payment = db_session.scalar(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id).limit(1)
    )
    assert payment is not None
    payments_before = int(
        db_session.scalar(
            select(func.count())
            .select_from(BookingPayment)
            .where(BookingPayment.booking_id == booking_id)
        )
        or 0
    )
    db_session.add(
        PaymentEvent(
            booking_payment_id=payment.id,
            event_type="test.simulated",
        )
    )
    db_session.flush()
    payment_events_before = int(
        db_session.scalar(
            select(func.count())
            .select_from(PaymentEvent)
            .where(
                PaymentEvent.booking_payment_id.in_(
                    select(BookingPayment.id).where(BookingPayment.booking_id == booking_id)
                )
            )
        )
        or 0
    )
    db_session.add(
        VenueBlackout(
            venue_space_id=context["space"].id,
            starts_at=datetime(2026, 12, 1, 10, tzinfo=UTC),
            ends_at=datetime(2026, 12, 1, 11, tzinfo=UTC),
            reason="teste",
        )
    )
    db_session.add(
        VenueBusinessHour(
            organization_venue_id=context["venue"].id,
            weekday=1,
            opens_at=time(6, 0),
            closes_at=time(22, 0),
        )
    )
    db_session.add(
        VenuePhoto(
            organization_venue_id=context["venue"].id,
            venue_space_id=context["space"].id,
            status="PENDING",
            storage_key=f"test/{uuid.uuid4()}",
            content_type="image/jpeg",
            size_bytes=100,
            width=10,
            height=10,
        )
    )

    platform = Organization(name="JOGA Público", is_platform=True)
    db_session.add(platform)
    db_session.flush()
    platform_venue = OrganizationVenue(
        organization_id=platform.id,
        name="Praça Pública",
        is_public=True,
    )
    db_session.add(platform_venue)
    db_session.flush()
    platform_space = VenueSpace(organization_venue_id=platform_venue.id, name="Quadra Pública")
    db_session.add(platform_space)
    db_session.flush()
    db_session.add(
        VenueAvailability(
            venue_space_id=platform_space.id,
            weekday=1,
            start_time=time(6, 0),
            end_time=time(22, 0),
            price_cents=0,
            slot_minutes=60,
        )
    )
    db_session.add(UserProfile(user_id=context["users"][0], display_name="Preservado"))
    db_session.commit()

    users_before = _count(db_session, User)
    lobbies_before = _count(db_session, Lobby)
    demo_org_id = context["organization"].id
    demo_venue_id = context["venue"].id
    demo_space_id = context["space"].id
    platform_org_id = platform.id
    platform_venue_id = platform_venue.id
    platform_space_id = platform_space.id

    counts = reset_demo_venues(db_session)
    db_session.commit()

    assert counts["bookings"] == 1
    assert counts["booking_payments"] == payments_before
    assert counts["payment_events"] == payment_events_before
    assert counts["venue_spaces"] == 1
    assert counts["venue_availability"] == 1
    assert counts["venue_blackouts"] == 1
    assert counts["venue_photos"] == 1
    assert counts["venue_business_hours"] == 1
    assert counts["organization_memberships"] == 1
    assert counts["organizations"] == 1
    assert db_session.scalar(select(Booking.id).where(Booking.id == booking_id)) is None
    assert db_session.scalar(select(Organization.id).where(Organization.id == demo_org_id)) is None
    assert (
        db_session.scalar(select(OrganizationVenue.id).where(OrganizationVenue.id == demo_venue_id))
        is None
    )
    assert db_session.scalar(select(VenueSpace.id).where(VenueSpace.id == demo_space_id)) is None

    assert db_session.get(Organization, platform_org_id) is not None
    assert db_session.get(OrganizationVenue, platform_venue_id) is not None
    assert db_session.get(VenueSpace, platform_space_id) is not None
    assert _count(db_session, User) == users_before
    assert _count(db_session, Lobby) == lobbies_before
    assert db_session.get(UserProfile, context["users"][0]) is not None

    again = reset_demo_venues(db_session)
    db_session.commit()
    assert sum(again.values()) == 0


def test_reset_requires_explicit_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOGA_ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        assert main([]) == 2
    finally:
        get_settings.cache_clear()


def test_reset_refuses_local_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOGA_ENVIRONMENT", "local")
    get_settings.cache_clear()
    try:
        assert main(["--yes"]) == 2
    finally:
        get_settings.cache_clear()
