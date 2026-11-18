"""Testes de T2 em horário comercial e reserva automática do lobby (Fase 13E)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from fastapi.testclient import TestClient
from sqlalchemy import select
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


def business_hours_url(context: dict) -> str:
    return (
        f"/api/v1/organizations/{context['organization'].id}"
        f"/venues/{context['venue'].id}/business-hours"
    )


def create_hour(
    api: TestClient,
    context: dict,
    *,
    weekday: int = 1,
    opens_at: str = "09:00:00",
    closes_at: str = "18:00:00",
) -> dict:
    response = api.post(
        business_hours_url(context),
        headers=bearer(context["owner_token"]),
        json={"weekday": weekday, "opens_at": opens_at, "closes_at": closes_at},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_business_hour_can_be_updated_without_recreating(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.modules.identity.models import AuditLog
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    created = create_hour(api, context)

    response = api.patch(
        f"{business_hours_url(context)}/{created['id']}",
        headers=bearer(context["owner_token"]),
        json={"weekday": 3, "opens_at": "10:00:00", "closes_at": "20:00:00"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == created["id"]
    assert body["weekday"] == 3
    assert body["opens_at"].startswith("10:00")
    assert body["closes_at"].startswith("20:00")

    listed = api.get(business_hours_url(context), headers=bearer(context["owner_token"]))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["business_hours"]] == [created["id"]]

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "venue_business_hour.updated")
    )
    assert audit is not None
    assert audit.details is not None
    assert audit.details["before"]["weekday"] == 1
    assert audit.details["after"]["weekday"] == 3


def test_business_hour_update_rejects_exact_duplicate(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    first = create_hour(api, context)
    create_hour(api, context, weekday=2, opens_at="09:00:00", closes_at="18:00:00")

    response = api.patch(
        f"{business_hours_url(context)}/{first['id']}",
        headers=bearer(context["owner_token"]),
        json={"weekday": 2},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "business_hour_conflict"


def test_business_hour_update_rejects_overlap(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    first = create_hour(api, context, opens_at="09:00:00", closes_at="12:00:00")
    create_hour(api, context, weekday=1, opens_at="14:00:00", closes_at="18:00:00")

    response = api.patch(
        f"{business_hours_url(context)}/{first['id']}",
        headers=bearer(context["owner_token"]),
        json={"closes_at": "15:00:00"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "business_hour_conflict"

    # Encostar sem sobrepor é permitido.
    allowed = api.patch(
        f"{business_hours_url(context)}/{first['id']}",
        headers=bearer(context["owner_token"]),
        json={"closes_at": "14:00:00"},
    )
    assert allowed.status_code == 200, allowed.text


def test_business_hour_update_rejects_invalid_window(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    created = create_hour(api, context)

    response = api.patch(
        f"{business_hours_url(context)}/{created['id']}",
        headers=bearer(context["owner_token"]),
        json={"opens_at": "18:00:00", "closes_at": "09:00:00"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_input"


def test_business_hour_update_hides_resource_from_other_organization(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.modules.organizations.models import Organization, OrganizationMembership
    from app.modules.organizations.permissions import Role
    from tests.test_ticket_settlement import api_client

    api = api_client(client, db_session)
    context = setup_context(db_session)
    created = create_hour(api, context)

    outsider_id = make_user(db_session)
    other = Organization(name="Outra Arena", legal_document="98765432000188")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=other.id,
            user_id=outsider_id,
            role=Role.OWNER.value,
        )
    )
    db_session.flush()
    from tests.helpers_results import make_token

    token = make_token(db_session, outsider_id)
    response = api.patch(
        f"{business_hours_url(context)}/{created['id']}",
        headers=bearer(token),
        json={"weekday": 4},
    )
    assert response.status_code == 404, response.text
