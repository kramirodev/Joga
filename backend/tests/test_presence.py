"""Testes de pré-check-in, presença e fechamento de no-show (ADR 0039)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingSubstitution
from app.modules.bookings.presence import (
    BookingPresenceService,
    PresenceForbidden,
    PresenceInvalid,
    PresenceWindowError,
    haversine_m,
)
from app.modules.profile.models import Venue
from tests.test_bookings_api import api_client, setup_booking
from tests.test_substitutions import aware, confirmed_booking


def link_catalog_venue(db_session: Session, context, lat: float, lng: float) -> Venue:
    catalog = Venue(
        name="Arena Centro",
        kind="private",
        city="Rio de Janeiro",
        state="RJ",
        lat=lat,
        lng=lng,
    )
    db_session.add(catalog)
    db_session.flush()
    context["venue"].venue_id = catalog.id
    db_session.flush()
    return catalog


def test_geofence_presence_and_close_marks_absent(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None
    link_catalog_venue(db_session, context, -22.9, -43.2)
    starts_at = aware(booking.starts_at)
    now = starts_at - timedelta(minutes=45)
    service = BookingPresenceService(db_session)

    pre = service.pre_check_in(context["users"][0], booking.id, now=now)
    assert pre.pre_checked_in_at is not None

    present = service.confirm(
        context["users"][0],
        booking.id,
        context["users"][0],
        method="GPS",
        latitude=-22.9,
        longitude=-43.2,
        accuracy_m=20,
        now=now,
    )
    assert present.presence_status == "PRESENT"
    assert present.presence_distance_m is not None
    assert present.presence_distance_m < 5

    far = service.confirm(
        context["users"][1],
        booking.id,
        context["users"][1],
        method="GPS",
        latitude=-22.89,
        longitude=-43.2,
        accuracy_m=20,
        now=now,
    )
    assert far.presence_status == "UNVERIFIED"

    no_shows = service.close_due(now=starts_at - timedelta(minutes=30))
    db_session.commit()
    assert no_shows == 3

    db_session.expire_all()
    booking = db_session.get(Booking, booking.id)
    assert booking is not None and booking.status == "CONFIRMED"
    assert booking.presence_closed_at is not None
    substitutions = db_session.scalars(
        select(BookingSubstitution).where(
            BookingSubstitution.booking_id == booking.id,
            BookingSubstitution.status == "OPEN",
        )
    ).all()
    assert len(substitutions) == 3
    assert {item.paid_seat for item in substitutions} == {True}
    assert db_session.scalar(select(func.count()).select_from(BookingSubstitution)) == 3


def test_gps_without_venue_coordinates_is_unverified(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None
    starts_at = aware(booking.starts_at)
    service = BookingPresenceService(db_session)

    participant = service.confirm(
        context["users"][0],
        booking.id,
        context["users"][0],
        method="GPS",
        latitude=-22.9,
        longitude=-43.2,
        accuracy_m=10,
        now=starts_at - timedelta(minutes=45),
    )
    assert participant.presence_status == "UNVERIFIED"

    confirmed = service.confirm(
        context["users"][0],
        booking.id,
        context["users"][0],
        method="VENUE",
        now=starts_at - timedelta(minutes=44),
    )
    assert confirmed.presence_status == "PRESENT"


def test_venue_confirms_other_but_captain_does_not_exist(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None
    link_catalog_venue(db_session, context, -22.9, -43.2)
    starts_at = aware(booking.starts_at)
    now = starts_at - timedelta(minutes=45)
    service = BookingPresenceService(db_session)

    with pytest.raises(PresenceForbidden):
        service.confirm(
            context["users"][0],
            booking.id,
            context["users"][1],
            method="GPS",
            latitude=-22.9,
            longitude=-43.2,
            accuracy_m=10,
            now=now,
        )
    db_session.rollback()

    with pytest.raises(PresenceInvalid):
        service.confirm(
            context["users"][0],
            booking.id,
            context["users"][1],
            method="CAPTAIN",
            now=now,
        )
    db_session.rollback()

    confirmed = service.confirm(
        context["users"][0],
        booking.id,
        context["users"][1],
        method="VENUE",
        now=now,
    )
    assert confirmed.presence_status == "PRESENT"


def test_pre_check_in_outside_window_is_rejected(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None
    with pytest.raises(PresenceWindowError):
        BookingPresenceService(db_session).pre_check_in(
            context["users"][0],
            booking.id,
            now=aware(booking.starts_at) - timedelta(hours=2),
        )
    db_session.rollback()


def test_haversine_distance_is_reasonable() -> None:
    assert haversine_m(-22.9, -43.2, -22.9, -43.2) == 0
    assert 100 < haversine_m(-22.9, -43.2, -22.899, -43.2) < 120
