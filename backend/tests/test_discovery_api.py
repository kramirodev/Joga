"""Testes da vitrine reservável e do portão de repasse (Fase 13C)."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking
from app.modules.pricing.service import resolve_band
from app.modules.profile.models import SportFormat
from app.modules.venues.models import VenueAvailability, VenueSport
from tests.test_ticket_settlement import START, bearer, setup_context


def api_client(client: TestClient, db_session: Session) -> TestClient:
    from tests.test_ticket_settlement import api_client as base_api_client

    return base_api_client(client, db_session)


def test_list_and_detail_expose_bookable_space_without_financial_data(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    format_ = db_session.get(SportFormat, context["lobby"].format_id)
    assert format_ is not None
    db_session.add(VenueSport(venue_space_id=context["space"].id, sport_id=format_.sport_id))
    db_session.flush()

    listing = api.get(
        "/api/v1/discovery/bookable-venues",
        headers=bearer(context["tokens"][0]),
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1
    card = body["venues"][0]
    assert card["id"] == str(context["venue"].id)
    assert card["covered"] is False
    assert card["spaces_count"] == 1
    assert card["min_price_cents"] == 12_000
    assert "payout" not in card
    assert "legal_document" not in card

    detail = api.get(
        f"/api/v1/discovery/bookable-venues/{context['venue'].id}",
        headers=bearer(context["tokens"][0]),
    )
    assert detail.status_code == 200, detail.text
    venue = detail.json()
    assert venue["name"] == "Arena Centro"
    assert len(venue["spaces"]) == 1
    space = venue["spaces"][0]
    assert space["name"] == "Quadra 1"
    assert space["next_slots"]
    assert space["availability"][0]["band"]["code"] == "economica_dia"
    assert space["sports"][0]["formats"][0]["tickets_by_band"]["economica_dia"] == 8
    assert "payout_ready" not in venue


def test_booking_creation_requires_payout_ready_and_exposes_ticket_context(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    format_ = db_session.get(SportFormat, context["lobby"].format_id)
    assert format_ is not None
    db_session.add(VenueSport(venue_space_id=context["space"].id, sport_id=format_.sport_id))
    db_session.flush()

    payload = {
        "lobby_id": str(context["lobby"].id),
        "organization_venue_id": str(context["venue"].id),
        "venue_space_id": str(context["space"].id),
        "starts_at": START.isoformat(),
        "ends_at": (START + timedelta(minutes=60)).isoformat(),
    }

    context["organization"].payout_status = "pending"
    db_session.commit()
    blocked = api.post(
        "/api/v1/bookings",
        headers=bearer(context["tokens"][0]),
        json=payload,
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "payout_not_ready"

    context["organization"].payout_status = "active"
    db_session.commit()
    created = api.post(
        "/api/v1/bookings",
        headers=bearer(context["tokens"][0]),
        json=payload,
    )
    assert created.status_code == 201, created.text
    booking = created.json()
    assert booking["organization_venue_name"] == "Arena Centro"
    assert booking["venue_space_name"] == "Quadra 1"
    assert booking["format_name"] == "Futebol 3x3"
    assert booking["band_code"] == "economica_dia"
    assert booking["tickets_per_seat"] == 8
    assert booking["participants"][0]["settled_with"] is None
    assert booking["participants"][0]["tickets_consumed"] == 0

    stored = db_session.get(Booking, UUID(booking["id"]))
    assert stored is not None
    assert stored.band_id is not None
    assert stored.tickets_per_seat == 8

    availability = db_session.scalar(
        select(VenueAvailability).where(VenueAvailability.venue_space_id == context["space"].id)
    )
    assert availability is not None
    availability.band_id = resolve_band(db_session, 15_000).id
    db_session.commit()

    after_reprice = api.get(
        f"/api/v1/bookings/{booking['id']}",
        headers=bearer(context["tokens"][0]),
    )
    assert after_reprice.status_code == 200, after_reprice.text
    assert after_reprice.json()["tickets_per_seat"] == 8
    assert after_reprice.json()["band_code"] == "economica_dia"


def test_unknown_venue_is_404(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    missing = api.get(
        "/api/v1/discovery/bookable-venues/00000000-0000-0000-0000-000000000000",
        headers=bearer(context["tokens"][0]),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "venue_not_found"
