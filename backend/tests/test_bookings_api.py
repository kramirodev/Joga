"""Testes HTTP de reservas, temporizadores e substituição (Fase 13A)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

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
from tests.settings_helpers import demo_settings, production_settings


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
    organization = Organization(
        name="Arena Reservas",
        legal_document="12345678000199",
        pix_key_type="cnpj",
        pix_key="12345678000199",
        payout_status="active",
    )
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
    assert booking["venue_price_cents"] == 40_000
    assert booking["fee_cents"] == 8_000
    assert booking["fee_percent_applied"] == 2_000
    assert booking["pricing_version"] == "adr0049_v1"
    assert booking["venue_price_cents"] + booking["fee_cents"] == booking["total_cents"]
    assert sum(item["contribution_cents"] for item in booking["participants"]) == 48_000
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


def _accepted_booking(api: TestClient, context: dict) -> dict:
    booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, booking["id"])
    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


def test_simulated_payment_is_allowed_in_demo_for_participant(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _accepted_booking(api, context)
    monkeypatch.setattr("app.modules.bookings.service.get_settings", demo_settings)

    paid = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(context["tokens"][0]),
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["payments"][0]["status"] == "PAID"

    outsider = make_user(db_session)
    forbidden = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(make_token(db_session, outsider)),
    )
    assert forbidden.status_code == 404
    assert forbidden.json() == {"detail": {"code": "booking_not_found"}}


def _confirmed_booking(api: TestClient, context: dict) -> dict:
    booking = _accepted_booking(api, context)
    latest: dict | None = None
    for token in context["tokens"]:
        paid = api.post(
            f"/api/v1/bookings/{booking['id']}/payments/simulate",
            headers=bearer(token),
        )
        assert paid.status_code == 200, paid.text
        latest = paid.json()
    assert latest is not None
    assert latest["status"] == "CONFIRMED"
    return latest


def test_simulate_payment_confirmed_booking_keeps_participant_access(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _confirmed_booking(api, context)

    replay = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(context["tokens"][2]),
    )

    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "CONFIRMED"


def test_simulate_payment_confirmed_booking_is_not_disclosed_to_outsider(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _confirmed_booking(api, context)
    outsider_token = make_token(db_session, make_user(db_session))

    response = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(outsider_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "booking_not_found"}}
    # O mesmo GET também não revela a reserva, com a mesma resposta do POST.
    read = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(outsider_token))
    assert read.status_code == 404
    assert read.json() == response.json()


def test_simulate_payment_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _confirmed_booking(api, context)

    response = api.post(f"/api/v1/bookings/{booking['id']}/payments/simulate")

    assert response.status_code == 401


def test_simulate_payment_missing_booking_is_indistinguishable_from_outsider(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _confirmed_booking(api, context)
    outsider_token = make_token(db_session, make_user(db_session))

    existing = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(outsider_token),
    )
    missing = api.post(
        f"/api/v1/bookings/{uuid4()}/payments/simulate",
        headers=bearer(outsider_token),
    )

    assert existing.status_code == missing.status_code == 404
    assert existing.json() == missing.json() == {"detail": {"code": "booking_not_found"}}


def test_simulate_payment_is_not_granted_to_non_participant_org_owner(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _confirmed_booking(api, context)
    manager = make_user(db_session)
    db_session.add(
        OrganizationMembership(
            organization_id=context["organization"].id,
            user_id=manager,
            role=Role.OWNER.value,
        )
    )
    db_session.flush()
    manager_token = make_token(db_session, manager)

    # A organização lê a reserva, mas o simulador é ação do jogador da vaga.
    read = api.get(f"/api/v1/bookings/{booking['id']}", headers=bearer(manager_token))
    assert read.status_code == 200

    response = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(manager_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "booking_not_found"}}


def test_simulated_payment_is_forbidden_in_production(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = _accepted_booking(api, context)
    monkeypatch.setattr("app.modules.bookings.service.get_settings", production_settings)

    response = api.post(
        f"/api/v1/bookings/{booking['id']}/payments/simulate",
        headers=bearer(context["tokens"][0]),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": {"code": "forbidden"}}


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


def test_booking_lists_expose_pagination_filters_and_timezone(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])
    org_id = context["organization"].id
    token = context["tokens"][0]

    listing = api.get(
        f"/api/v1/organizations/{org_id}/bookings?limit=1&offset=0",
        headers=bearer(token),
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["bookings"]) == 1
    assert body["bookings"][0]["id"] == booking["id"]
    assert body["bookings"][0]["timezone"] == "UTC"

    filtered = api.get(
        f"/api/v1/organizations/{org_id}/bookings?status=PARTICIPANT_CONFIRMATION",
        headers=bearer(token),
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1

    empty = api.get(
        f"/api/v1/organizations/{org_id}/bookings?status=CONFIRMED",
        headers=bearer(token),
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["total"] == 0

    in_period = api.get(
        f"/api/v1/organizations/{org_id}/bookings"
        f"?from={START.isoformat().replace('+00:00', 'Z')}"
        f"&to={END.isoformat().replace('+00:00', 'Z')}",
        headers=bearer(token),
    )
    assert in_period.status_code == 200, in_period.text
    assert in_period.json()["total"] == 1

    out_of_period = api.get(
        f"/api/v1/organizations/{org_id}/bookings"
        f"?from={(START + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}"
        f"&to={(START + timedelta(days=2)).isoformat().replace('+00:00', 'Z')}",
        headers=bearer(token),
    )
    assert out_of_period.status_code == 200, out_of_period.text
    assert out_of_period.json()["total"] == 0

    invalid_period = api.get(
        f"/api/v1/organizations/{org_id}/bookings"
        f"?from={START.isoformat().replace('+00:00', 'Z')}"
        f"&to={START.isoformat().replace('+00:00', 'Z')}",
        headers=bearer(token),
    )
    assert invalid_period.status_code == 422
    assert invalid_period.json()["detail"]["code"] == "invalid_time_range"

    mine = api.get("/api/v1/bookings?limit=1", headers=bearer(token))
    assert mine.status_code == 200, mine.text
    assert mine.json()["total"] == 1
    assert mine.json()["bookings"][0]["timezone"] == "UTC"
