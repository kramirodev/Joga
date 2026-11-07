"""Testes HTTP de reservas, temporizadores e substituição (Fase 13A)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.bookings.service import BookingService
from app.modules.identity.clock import utcnow
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.venues.models import VenueAvailability, VenueSpace
from tests.helpers_results import make_format, make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


START = datetime(2026, 12, 15, 18, 0, tzinfo=UTC)
END = START + timedelta(minutes=60)


def setup_booking(
    db_session: Session,
    *,
    lobby_count: int = 1,
) -> dict:
    users = [make_user(db_session) for _ in range(4)]
    _, format_ = make_format(db_session, team_size=2)
    organization = Organization(name="Arena Reservas")
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
    db_session.add(
        VenueAvailability(
            venue_space_id=space.id,
            weekday=START.isoweekday(),
            start_time=time(17, 0),
            end_time=time(23, 0),
            price_cents=40_000,
            slot_minutes=60,
        )
    )

    lobbies: list[Lobby] = []
    for _index in range(lobby_count):
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
                    team=1 if seat <= 2 else 2,
                    level="intermediate",
                )
            )
        lobbies.append(lobby)
    db_session.flush()
    tokens = [make_token(db_session, user_id) for user_id in users]
    return {
        "users": users,
        "tokens": tokens,
        "organization": organization,
        "venue": venue,
        "space": space,
        "lobbies": lobbies,
    }


def create_booking(api: TestClient, context: dict, lobby: Lobby) -> dict:
    response = api.post(
        "/api/v1/bookings",
        headers=bearer(context["tokens"][0]),
        json={
            "lobby_id": str(lobby.id),
            "organization_venue_id": str(context["venue"].id),
            "venue_space_id": str(context["space"].id),
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_all(api: TestClient, context: dict, booking_id: str) -> dict:
    result = None
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking_id}/participant-confirmation",
            headers=bearer(token),
            json={"decision": "CONFIRM"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
    assert result is not None
    return result


def test_happy_path_t1_t2_t3(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])
    assert booking["status"] == "PARTICIPANT_CONFIRMATION"
    assert sum(item["contribution_cents"] for item in booking["participants"]) == 40_000
    assert booking["timers"][0]["timer_type"] == "T1"

    requested = confirm_all(api, context, booking["id"])
    assert requested["status"] == "REQUESTED"
    assert {timer["timer_type"] for timer in requested["timers"]} == {"T1", "T2"}

    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    assert accepted_body["status"] == "PAYMENT_PENDING"
    assert accepted_body["hold"]["status"] == "ACTIVE"
    assert {payment["status"] for payment in accepted_body["payments"]} == {"PENDING"}
    assert len(accepted_body["payments"]) == 4

    player_view = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(context["tokens"][1]))
    assert player_view.status_code == 200
    player_body = player_view.json()
    assert len(player_body["payments"]) == 1
    for participant in player_body["participants"]:
        if participant["user_id"] != str(context["users"][1]):
            assert participant["payment_status"] == "HIDDEN"

    for token in context["tokens"]:
        paid = api.post(
            f"/api/v1/bookings/{booking['id']}/payments/simulate",
            headers=bearer(token),
        )
        assert paid.status_code == 200, paid.text

    confirmed = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(context["tokens"][0]))
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "CONFIRMED"
    assert body["hold"]["status"] == "RELEASED"
    assert {item["payment_status"] for item in body["participants"]} == {"PAID"}


def test_accept_before_confirmation_and_payment_before_accept_are_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])

    early_accept = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert early_accept.status_code == 409
    assert early_accept.json()["detail"]["code"] == "invalid_transition"

    early_payment = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(context["tokens"][0]),
    )
    assert early_payment.status_code == 409


def test_decline_and_substitution_keep_four_active_seats(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])

    declined = api.post(
        f"/api/v1/bookings/{booking['id']}/participant-confirmation",
        headers=bearer(context["tokens"][1]),
        json={"decision": "DECLINE"},
    )
    assert declined.status_code == 200
    assert len([item for item in declined.json()["participants"] if item["active"]]) == 3

    substitute_user = make_user(db_session)
    substituted = api.post(
        f"/api/v1/bookings/{booking['id']}/substitutions",
        headers=bearer(context["tokens"][0]),
        json={
            "replace_user_id": str(context["users"][1]),
            "new_user_id": str(substitute_user),
        },
    )
    assert substituted.status_code == 200, substituted.text
    active = [item for item in substituted.json()["participants"] if item["active"]]
    assert len(active) == 4
    assert {item["seat"] for item in active} == {1, 2, 3, 4}

    substitute_token = make_token(db_session, substitute_user)
    for token in [
        context["tokens"][0],
        context["tokens"][2],
        context["tokens"][3],
        substitute_token,
    ]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/participant-confirmation",
            headers=bearer(token),
            json={"decision": "CONFIRM"},
        )
        assert response.status_code == 200, response.text
    final = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(context["tokens"][0]))
    assert final.json()["status"] == "REQUESTED"


def test_expiry_of_t1_t2_and_t3(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    service = BookingService(db_session)

    context = setup_booking(db_session)
    t1_booking = create_booking(api, context, context["lobbies"][0])
    assert service.expire_due(now=utcnow() + timedelta(hours=2)) == 1
    db_session.commit()
    expired = api.get(f"/api/v1/bookings/{t1_booking['id']}", headers=bearer(context["tokens"][0]))
    assert expired.json()["status"] == "EXPIRED"

    context = setup_booking(db_session)
    t2_booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, t2_booking["id"])
    assert service.expire_due(now=utcnow() + timedelta(hours=2)) == 1
    db_session.commit()
    expired = api.get(f"/api/v1/bookings/{t2_booking['id']}", headers=bearer(context["tokens"][0]))
    assert expired.json()["status"] == "EXPIRED"

    context = setup_booking(db_session)
    t3_booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, t3_booking["id"])
    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{t3_booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200
    assert service.expire_due(now=utcnow() + timedelta(hours=2)) == 1
    db_session.commit()
    expired = api.get(f"/api/v1/bookings/{t3_booking['id']}", headers=bearer(context["tokens"][0]))
    assert expired.json()["status"] == "CANCELLED"
    assert expired.json()["hold"]["status"] == "EXPIRED"


def test_second_hold_for_same_space_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session, lobby_count=2)
    first = create_booking(api, context, context["lobbies"][0])
    second = create_booking(api, context, context["lobbies"][1])
    confirm_all(api, context, first["id"])
    confirm_all(api, context, second["id"])

    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{first['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text

    conflict = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{second['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "space_unavailable"


def test_outsider_cannot_read_or_confirm_booking(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])
    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)

    read = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(outsider_token))
    assert read.status_code == 404

    confirm = api.post(
        f"/api/v1/bookings/{booking['id']}/participant-confirmation",
        headers=bearer(outsider_token),
        json={"decision": "CONFIRM"},
    )
    assert confirm.status_code == 403

    listing = api.get("/api/v1/bookings", headers=bearer(outsider_token))
    assert listing.status_code == 200
    assert listing.json()["bookings"] == []


def test_booking_creation_is_idempotent_per_lobby(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    first = create_booking(api, context, context["lobbies"][0])
    second = create_booking(api, context, context["lobbies"][0])
    assert first["id"] == second["id"]
