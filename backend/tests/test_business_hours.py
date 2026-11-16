"""Testes de T2 em horário comercial e reserva automática do lobby (Fase 13E)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.profile.models import SportFormat
from app.modules.venues.business_hours import add_business_minutes, business_deadline
from app.modules.venues.models import VenueBusinessHour, VenueClosure, VenueSport
from tests.helpers_results import make_user
from tests.test_ticket_settlement import bearer, setup_context


def hours(*weekdays: int) -> list[VenueBusinessHour]:
    return [
        VenueBusinessHour(
            organization_venue_id=uuid.uuid4(),
            weekday=weekday,
            opens_at=time(9, 0),
            closes_at=time(18, 0),
        )
        for weekday in weekdays
    ]


def test_business_minutes_skip_closed_days_and_closures() -> None:
    monday = datetime(2026, 11, 16, 17, 45, tzinfo=UTC)  # segunda-feira
    schedule = hours(1, 2, 3)
    closure = VenueClosure(
        organization_venue_id=uuid.uuid4(),
        starts_at=datetime(2026, 11, 17, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 11, 18, 0, 0, tzinfo=UTC),
        reason="Feriado",
    )

    assert add_business_minutes(monday, 30, schedule, [], timezone="UTC") == datetime(
        2026, 11, 17, 9, 15, tzinfo=UTC
    )

    skipped = add_business_minutes(monday, 30, schedule, [closure], timezone="UTC")
    assert skipped == datetime(2026, 11, 18, 9, 15, tzinfo=UTC)


def test_business_deadline_is_capped_by_elapsed_limit() -> None:
    monday = datetime(2026, 11, 16, 17, 45, tzinfo=UTC)
    deadline = business_deadline(
        monday,
        30,
        60,
        hours(1, 2, 3),
        [],
        timezone="UTC",
    )
    assert deadline == datetime(2026, 11, 16, 18, 45, tzinfo=UTC)


def test_business_minutes_fall_back_without_schedule() -> None:
    start = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
    assert add_business_minutes(start, 30, [], [], timezone="UTC") == datetime(
        2026, 11, 16, 10, 30, tzinfo=UTC
    )


def test_from_lobby_chooses_a_bookable_space(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    format_ = db_session.get(SportFormat, context["lobby"].format_id)
    assert format_ is not None
    db_session.add(VenueSport(venue_space_id=context["space"].id, sport_id=format_.sport_id))
    db_session.flush()

    response = api.post(
        "/api/v1/bookings/from-lobby",
        headers=bearer(context["tokens"][0]),
        json={"lobby_id": str(context["lobby"].id)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["organization_venue_id"] == str(context["venue"].id)
    assert body["venue_space_id"] == str(context["space"].id)
    assert body["tickets_per_seat"] == 8


def test_from_lobby_without_sport_link_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)

    response = api.post(
        "/api/v1/bookings/from-lobby",
        headers=bearer(context["tokens"][0]),
        json={"lobby_id": str(context["lobby"].id)},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "no_bookable_space"


def test_business_hours_api_requires_manage_for_write(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    owner_id = make_user(db_session)
    # O usuário criado não é membro da organização; o service deve negar.
    from tests.helpers_results import make_token

    token = make_token(db_session, owner_id)
    response = api.post(
        f"/api/v1/organizations/{context['organization'].id}/venues/{context['venue'].id}/business-hours",
        headers=bearer(token),
        json={"weekday": 1, "opens_at": "09:00:00", "closes_at": "18:00:00"},
    )
    assert response.status_code == 404
