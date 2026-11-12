"""Testes de quitação por ingressos (Fase 14D.5, modelo A)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import BookingParticipant
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.pricing.service import resolve_band
from app.modules.tickets.service import get_balance, grant
from app.modules.venues.models import VenueAvailability, VenueSpace
from tests.helpers_results import make_format, make_token, make_user

START = datetime(2026, 12, 15, 18, 0, tzinfo=UTC)
END = START + timedelta(minutes=60)
TEAM_SIZE = 3
SEATS = TEAM_SIZE * 2
PRICE_CENTS = 12_000
TICKETS_PER_SEAT = 8  # economica_dia, team_size 3


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_context(db_session: Session, *, tickets: int = TICKETS_PER_SEAT) -> dict:
    users = [make_user(db_session) for _ in range(SEATS)]
    _, format_ = make_format(db_session, team_size=TEAM_SIZE)
    organization = Organization(name="Arena Ingresso")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=users[0],
            role=Role.OWNER.value,
        )
    )
    venue = OrganizationVenue(
        organization_id=organization.id,
        name="Arena Centro",
        timezone="UTC",
    )
    db_session.add(venue)
    db_session.flush()
    space = VenueSpace(organization_venue_id=venue.id, name="Quadra 1")
    db_session.add(space)
    db_session.flush()
    band = resolve_band(db_session, PRICE_CENTS)
    db_session.add(
        VenueAvailability(
            venue_space_id=space.id,
            weekday=START.isoweekday(),
            start_time=time(17, 0),
            end_time=time(23, 0),
            price_cents=PRICE_CENTS,
            slot_minutes=60,
            band_id=band.id,
        )
    )
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
    db_session.add(lobby)
    db_session.flush()
    for seat, user_id in enumerate(users, start=1):
        db_session.add(
            LobbyParticipant(
                lobby_id=lobby.id,
                user_id=user_id,
                team=1 if seat <= TEAM_SIZE else 2,
                level="intermediate",
            )
        )
    for user_id in users:
        grant(
            db_session,
            user_id,
            tickets,
            source="purchase",
            idempotency_key=f"purchase:{user_id}",
        )
    db_session.flush()
    return {
        "users": users,
        "tokens": [make_token(db_session, user_id) for user_id in users],
        "organization": organization,
        "venue": venue,
        "space": space,
        "lobby": lobby,
    }


def open_booking(api: TestClient, context: dict) -> dict:
    created = api.post(
        "/api/v1/bookings",
        headers=bearer(context["tokens"][0]),
        json={
            "lobby_id": str(context["lobby"].id),
            "organization_venue_id": str(context["venue"].id),
            "venue_space_id": str(context["space"].id),
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    booking = created.json()

    for token in context["tokens"]:
        confirmed = api.post(
            f"/api/v1/bookings/{booking['id']}/participant-confirmation",
            headers=bearer(token),
            json={"decision": "CONFIRM"},
        )
        assert confirmed.status_code == 200, confirmed.text

    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "PAYMENT_PENDING"
    return accepted.json()


def test_each_participant_settles_own_seat(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    booking = open_booking(api, context)

    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets", headers=bearer(token)
        )
        assert response.status_code == 200, response.text

    final = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(context["tokens"][0]))
    assert final.status_code == 200
    assert final.json()["status"] == "CONFIRMED"

    for user_id in context["users"]:
        assert get_balance(db_session, user_id) == 0

    participants = db_session.scalars(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == uuid.UUID(booking["id"])
        )
    ).all()
    assert {item.tickets_consumed for item in participants} == {TICKETS_PER_SEAT}
    assert {item.settled_with for item in participants} == {"tickets"}


def test_settlement_is_idempotent(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    booking = open_booking(api, context)
    token = context["tokens"][0]

    first = api.post(
        f"/api/v1/bookings/{booking['id']}/settle-with-tickets", headers=bearer(token)
    )
    second = api.post(
        f"/api/v1/bookings/{booking['id']}/settle-with-tickets", headers=bearer(token)
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert get_balance(db_session, context["users"][0]) == TICKETS_PER_SEAT - TICKETS_PER_SEAT


def test_insufficient_tickets_blocks_settlement(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session, tickets=TICKETS_PER_SEAT - 1)
    booking = open_booking(api, context)

    response = api.post(
        f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
        headers=bearer(context["tokens"][0]),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "insufficient_tickets"

    current = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(context["tokens"][0]))
    assert current.json()["status"] == "PAYMENT_PENDING"
