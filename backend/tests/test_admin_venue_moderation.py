"""Moderação global de quadras pela plataforma (ADR 0063)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.identity.models import AuditLog
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.profile.models import SportFormat
from app.modules.venues.models import VenueAvailability, VenueSpace, VenueSport
from tests.helpers_results import make_format, make_token, make_user

START = datetime(2026, 12, 15, 18, 0, tzinfo=UTC)
SLOT = timedelta(minutes=60)


def api_client(
    client: TestClient, db_session: Session, *, admin_id: UUID | None = None
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    settings = Settings(
        _env_file=None,
        platform_admins=str(admin_id) if admin_id is not None else "",
        ticket_purchase_enabled=True,
    )
    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_setup(db_session: Session) -> tuple[UUID, dict[str, str]]:
    admin_id = make_user(db_session)
    return admin_id, bearer(make_token(db_session, admin_id))


def seed_venue(
    db_session: Session,
    *,
    venue_name: str,
    organization: Organization | None = None,
    is_public: bool = False,
    status: str = "active",
    with_space: bool = True,
) -> dict:
    organization = organization or Organization(
        name="Arena Privada",
        legal_document="12345678000199",
        verification_status="verified",
        pix_key_type="cnpj",
        pix_key="12345678000199",
        payout_status="active",
    )
    if organization.id is None:
        db_session.add(organization)
        db_session.flush()
    venue = OrganizationVenue(
        organization_id=organization.id,
        name=venue_name,
        city="Rio de Janeiro",
        state="RJ",
        address_line="Rua das Quadras, 10",
        latitude=-22.9,
        longitude=-43.2,
        timezone="UTC",
        is_public=is_public,
        status=status,
    )
    db_session.add(venue)
    db_session.flush()
    space = None
    sport = None
    format_ = None
    if with_space:
        sport, format_ = make_format(db_session, team_size=2)
        space = VenueSpace(
            organization_venue_id=venue.id,
            name="Quadra 1",
            format_id=format_.id,
            price_cents=40_000,
            status="active",
        )
        db_session.add(space)
        db_session.flush()
        db_session.add(VenueSport(venue_space_id=space.id, sport_id=sport.id))
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
    db_session.commit()
    return {
        "organization": organization,
        "venue": venue,
        "space": space,
        "sport": sport,
        "format": format_,
    }


def make_lobby(
    db_session: Session, *, format_: SportFormat, users: list[UUID], starts_at: datetime
) -> Lobby:
    lobby = Lobby(
        format_id=format_.id,
        format_version=1,
        origin="manual",
        mode="casual",
        status="scheduled",
        court_preference="PRIVATE_ONLY",
        scheduled_start_at=starts_at,
        scheduled_end_at=starts_at + SLOT,
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
    db_session.commit()
    return lobby


def create_booking(
    api: TestClient, token: str, *, venue: OrganizationVenue, space: VenueSpace, lobby: Lobby
) -> object:
    starts_at = lobby.scheduled_start_at
    ends_at = lobby.scheduled_end_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)
    return api.post(
        "/api/v1/bookings",
        headers=bearer(token),
        json={
            "lobby_id": str(lobby.id),
            "organization_venue_id": str(venue.id),
            "venue_space_id": str(space.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
    )


def test_admin_lists_venues_from_any_organization_with_filters(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    first = Organization(
        name="Arena Alfa Ltda",
        legal_document="12345678000199",
        pix_key_type="cnpj",
        pix_key="12345678000199",
        payout_status="active",
    )
    second = Organization(name="Arena Beta Ltda")
    db_session.add_all([first, second])
    db_session.flush()

    alfa = seed_venue(
        db_session,
        venue_name="Arena Alfa Centro",
        organization=first,
        is_public=True,
    )
    beta = seed_venue(db_session, venue_name="Arena Beta Zona Sul", organization=first)
    gamma = seed_venue(
        db_session, venue_name="Arena Gama Suspensa", organization=first, status="inactive"
    )
    delta = seed_venue(db_session, venue_name="Arena Delta", organization=second)

    response = api.get("/api/v1/admin/venues", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 20
    listed = {item["id"]: item for item in body["venues"]}
    assert set(listed) == {
        str(alfa["venue"].id),
        str(beta["venue"].id),
        str(gamma["venue"].id),
        str(delta["venue"].id),
    }
    alfa_card = listed[str(alfa["venue"].id)]
    assert alfa_card["organization_name"] == "Arena Alfa Ltda"
    assert alfa_card["organization_is_platform"] is False
    assert alfa_card["organization_status"] == "active"
    assert alfa_card["is_public"] is True
    assert alfa_card["spaces_count"] == 1
    assert alfa_card["active_spaces_count"] == 1
    assert alfa_card["created_at"]
    assert alfa_card["updated_at"]

    page_one = api.get("/api/v1/admin/venues", headers=headers, params={"page": 1, "page_size": 2})
    assert page_one.status_code == 200
    assert page_one.json()["total"] == 4
    assert len(page_one.json()["venues"]) == 2
    page_two = api.get("/api/v1/admin/venues", headers=headers, params={"page": 2, "page_size": 2})
    assert len(page_two.json()["venues"]) == 2
    assert {item["id"] for item in page_one.json()["venues"]}.isdisjoint(
        {item["id"] for item in page_two.json()["venues"]}
    )

    by_name = api.get("/api/v1/admin/venues", headers=headers, params={"q": "beta"})
    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1
    assert by_name.json()["venues"][0]["name"] == "Arena Beta Zona Sul"

    by_status = api.get("/api/v1/admin/venues", headers=headers, params={"status": "inactive"})
    assert by_status.status_code == 200
    assert [item["id"] for item in by_status.json()["venues"]] == [str(gamma["venue"].id)]

    by_active = api.get("/api/v1/admin/venues", headers=headers, params={"active": "false"})
    assert [item["id"] for item in by_active.json()["venues"]] == [str(gamma["venue"].id)]

    public_only = api.get("/api/v1/admin/venues", headers=headers, params={"is_public": "true"})
    assert [item["id"] for item in public_only.json()["venues"]] == [str(alfa["venue"].id)]

    by_org = api.get(
        "/api/v1/admin/venues",
        headers=headers,
        params={"organization_id": str(second.id)},
    )
    assert [item["id"] for item in by_org.json()["venues"]] == [str(delta["venue"].id)]

    invalid_status = api.get("/api/v1/admin/venues", headers=headers, params={"status": "deleted"})
    assert invalid_status.status_code == 422


def test_suspend_removes_from_discovery_and_blocks_new_bookings_without_deleting(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    context = seed_venue(db_session, venue_name="Arena Moderada")
    venue = context["venue"]
    space = context["space"]
    format_ = context["format"]
    users = [make_user(db_session) for _ in range(4)]
    db_session.commit()

    discovery = api.get("/api/v1/discovery/bookable-venues", headers=headers)
    assert discovery.status_code == 200, discovery.text
    assert [item["id"] for item in discovery.json()["venues"]] == [str(venue.id)]

    first_lobby = make_lobby(db_session, format_=format_, users=users, starts_at=START)
    first_booking = create_booking(
        api, make_token(db_session, users[0]), venue=venue, space=space, lobby=first_lobby
    )
    assert first_booking.status_code == 201, first_booking.text
    booking_id = UUID(first_booking.json()["id"])

    suspended = api.post(
        f"/api/v1/admin/venues/{venue.id}/suspend",
        headers=headers,
        json={"reason": "violação das regras da plataforma"},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "inactive"

    assert api.get("/api/v1/discovery/bookable-venues", headers=headers).json()["venues"] == []
    detail = api.get(f"/api/v1/discovery/bookable-venues/{venue.id}", headers=headers)
    assert detail.status_code == 404
    assert detail.json() == {"detail": {"code": "venue_not_found"}}

    blocked_lobby = make_lobby(db_session, format_=format_, users=users, starts_at=START + SLOT)
    blocked = create_booking(
        api, make_token(db_session, users[0]), venue=venue, space=space, lobby=blocked_lobby
    )
    assert blocked.status_code == 422
    assert blocked.json() == {"detail": {"code": "invalid_input"}}

    db_session.expire_all()
    assert db_session.get(OrganizationVenue, venue.id) is not None
    assert db_session.get(VenueSpace, space.id) is not None
    assert db_session.get(Booking, booking_id) is not None

    reactivated = api.post(
        f"/api/v1/admin/venues/{venue.id}/reactivate",
        headers=headers,
        json={"reason": "revisão concluída"},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["status"] == "active"
    assert [
        item["id"]
        for item in api.get("/api/v1/discovery/bookable-venues", headers=headers).json()["venues"]
    ] == [str(venue.id)]

    allowed_lobby = make_lobby(db_session, format_=format_, users=users, starts_at=START + SLOT * 2)
    allowed = create_booking(
        api, make_token(db_session, users[0]), venue=venue, space=space, lobby=allowed_lobby
    )
    assert allowed.status_code == 201, allowed.text


def test_moderation_requires_platform_capability(client: TestClient, db_session: Session) -> None:
    admin_id, admin_headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    context = seed_venue(db_session, venue_name="Arena Alheia")
    venue = context["venue"]

    owner_id = make_user(db_session)
    operator_id = make_user(db_session)
    player_id = make_user(db_session)
    db_session.add_all(
        [
            OrganizationMembership(
                organization_id=context["organization"].id,
                user_id=owner_id,
                role="OWNER",
            ),
            OrganizationMembership(
                organization_id=context["organization"].id,
                user_id=operator_id,
                role="OPERATOR",
            ),
        ]
    )
    db_session.commit()

    assert api.get("/api/v1/admin/venues").status_code == 401
    for user_id in (owner_id, operator_id, player_id):
        user_headers = bearer(make_token(db_session, user_id))
        assert api.get("/api/v1/admin/venues", headers=user_headers).status_code == 403
        assert (
            api.post(
                f"/api/v1/admin/venues/{venue.id}/suspend",
                headers=user_headers,
                json={"reason": "tentativa de membro"},
            ).status_code
            == 403
        )
        assert (
            api.post(
                f"/api/v1/admin/venues/{venue.id}/reactivate",
                headers=user_headers,
                json={"reason": "tentativa de membro"},
            ).status_code
            == 403
        )
        assert (
            api.patch(
                f"/api/v1/admin/venues/{venue.id}",
                headers=user_headers,
                json={"name": "Não pode", "reason": "tentativa de membro"},
            ).status_code
            == 403
        )

    assert api.get("/api/v1/admin/venues", headers=admin_headers).status_code == 200


def test_audit_records_actor_reason_and_diff_and_patch_ignores_price(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    context = seed_venue(db_session, venue_name="Arena Auditada")
    venue = context["venue"]
    space = context["space"]

    suspended = api.post(
        f"/api/v1/admin/venues/{venue.id}/suspend",
        headers=headers,
        json={"reason": "  publicidade irregular  "},
    )
    assert suspended.status_code == 200, suspended.text

    patched = api.patch(
        f"/api/v1/admin/venues/{venue.id}",
        headers=headers,
        json={
            "name": "Arena Auditada Centro",
            "is_public": True,
            "price_cents": 1,
            "reason": "correção cadastral",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Arena Auditada Centro"
    assert patched.json()["is_public"] is True

    reactivated = api.post(
        f"/api/v1/admin/venues/{venue.id}/reactivate",
        headers=headers,
        json={"reason": "correção concluída"},
    )
    assert reactivated.status_code == 200, reactivated.text

    db_session.expire_all()
    assert db_session.get(VenueSpace, space.id).price_cents == 40_000

    events = list(
        db_session.scalars(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "organization_venue",
                AuditLog.resource_id == str(venue.id),
            )
            .order_by(AuditLog.created_at, AuditLog.id)
        ).all()
    )
    by_action = {event.action: event for event in events}
    assert set(by_action) >= {
        "admin.venue.suspended",
        "admin.venue.updated",
        "admin.venue.reactivated",
    }

    suspended_event = by_action["admin.venue.suspended"]
    assert suspended_event.actor_user_id == admin_id
    assert suspended_event.organization_id == context["organization"].id
    assert suspended_event.reason == "publicidade irregular"
    assert suspended_event.details["changes"] == {"status": {"from": "active", "to": "inactive"}}
    assert suspended_event.details["venue_name"] == "Arena Auditada"
    assert suspended_event.details["ip_hash"]

    update_event = by_action["admin.venue.updated"]
    assert update_event.reason == "correção cadastral"
    assert update_event.actor_user_id == admin_id
    assert update_event.details["changes"]["name"] == {
        "from": "Arena Auditada",
        "to": "Arena Auditada Centro",
    }
    assert update_event.details["changes"]["is_public"] == {"from": False, "to": True}
    assert "price_cents" not in update_event.details["changes"]

    reactivated_event = by_action["admin.venue.reactivated"]
    assert reactivated_event.reason == "correção concluída"
    assert reactivated_event.details["changes"]["status"] == {
        "from": "inactive",
        "to": "active",
    }


def test_detail_and_spaces_are_visible_for_third_party_venue(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    context = seed_venue(db_session, venue_name="Arena Detalhe")
    venue = context["venue"]
    space = context["space"]

    detail = api.get(f"/api/v1/admin/venues/{venue.id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["organization_name"] == "Arena Privada"
    assert detail.json()["spaces"][0]["id"] == str(space.id)
    assert detail.json()["spaces"][0]["sport_id"] == str(context["sport"].id)

    spaces = api.get(f"/api/v1/admin/venues/{venue.id}/spaces", headers=headers)
    assert spaces.status_code == 200, spaces.text
    assert [item["id"] for item in spaces.json()] == [str(space.id)]

    missing = api.get(f"/api/v1/admin/venues/{uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json() == {"detail": {"code": "venue_not_found"}}


def test_state_actions_require_reason(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    context = seed_venue(db_session, venue_name="Arena Sem Motivo")
    venue = context["venue"]

    blank = api.post(
        f"/api/v1/admin/venues/{venue.id}/suspend",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422
    assert blank.json() == {"detail": {"code": "reason_required"}}

    missing = api.post(f"/api/v1/admin/venues/{venue.id}/suspend", headers=headers, json={})
    assert missing.status_code == 422

    short = api.post(
        f"/api/v1/admin/venues/{venue.id}/suspend",
        headers=headers,
        json={"reason": "x"},
    )
    assert short.status_code == 422

    too_long = api.post(
        f"/api/v1/admin/venues/{venue.id}/reactivate",
        headers=headers,
        json={"reason": "x" * 501},
    )
    assert too_long.status_code == 422
