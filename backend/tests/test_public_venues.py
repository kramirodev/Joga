"""Quadras públicas da organização da plataforma."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.geo import get_postal_code_service
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.geo.service import PostalCodeResult
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.profile.cep import PostalCodeLocation
from app.modules.venues.models import VenueSpace
from tests.helpers_results import make_format, make_token, make_user

START = datetime(2026, 12, 15, 20, 0, tzinfo=UTC)
END = START + timedelta(minutes=60)


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


def create_catalog(api: TestClient, headers: dict[str, str]) -> dict:
    response = api.post(
        "/api/v1/admin/sports",
        headers=headers,
        json={
            "slug": "futebol",
            "name": "Futebol",
            "icon_key": "icon-sport-futebol-5x5",
            "sort_order": 10,
            "formats": [
                {
                    "slug": "futebol-5x5",
                    "name": "Futebol 5x5",
                    "team_size": 5,
                    "duration_minutes": 60,
                    "period_count": 1,
                    "score_model": "goals",
                    "positions": [],
                }
            ],
            "reason": "catálogo público",
        },
    )
    assert response.status_code == 201, response.text
    sport = response.json()
    activated = api.post(
        "/api/v1/admin/sports/futebol/activate",
        headers=headers,
        json={"reason": "publicar catálogo"},
    )
    assert activated.status_code == 200, activated.text
    return sport


def create_venue(
    api: TestClient, headers: dict[str, str], *, with_coordinates: bool = True
) -> dict:
    payload: dict[str, object] = {
        "name": "Quadra da Praia",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "address_line": "Avenida Atlântica, 100",
        "is_public": True,
        "reason": "quadra pública de teste",
    }
    if with_coordinates:
        payload["latitude"] = -22.9
        payload["longitude"] = -43.2
    response = api.post("/api/v1/admin/venues", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def add_space(
    api: TestClient,
    headers: dict[str, str],
    venue_id: str,
    *,
    sport: dict,
    price_cents: int = 12_000,
) -> dict:
    response = api.post(
        f"/api/v1/admin/venues/{venue_id}/spaces",
        headers=headers,
        json={
            "name": "Quadra 1",
            "sport_id": sport["id"],
            "format_id": sport["formats"][0]["id"],
            "price_cents": price_cents,
            "status": "active",
            "reason": "espaço público de teste",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_availability(
    api: TestClient, headers: dict[str, str], venue_id: str, space_id: str
) -> dict:
    response = api.post(
        f"/api/v1/admin/venues/{venue_id}/availability",
        headers=headers,
        json={
            "space_id": space_id,
            "weekday": START.isoweekday(),
            "start_time": "17:00:00",
            "end_time": "23:00:00",
            "price_cents": 12_000,
            "slot_minutes": 60,
            "reason": "agenda pública",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def publish_venue(api: TestClient, headers: dict[str, str], venue_id: str) -> dict:
    response = api.post(
        f"/api/v1/admin/venues/{venue_id}/activate",
        headers=headers,
        json={"reason": "publicar quadra pública"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_public_venue_appears_in_discovery_and_accepts_booking(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)
    venue = create_venue(api, headers)
    assert venue["status"] == "inactive"
    space = add_space(api, headers, venue["id"], sport=sport)
    add_availability(api, headers, venue["id"], space["id"])
    published = publish_venue(api, headers, venue["id"])
    assert published["status"] == "active"
    assert published["is_public"] is True

    discovery = api.get("/api/v1/discovery/bookable-venues", headers=headers)
    assert discovery.status_code == 200, discovery.text
    cards = discovery.json()["venues"]
    assert [item["name"] for item in cards] == ["Quadra da Praia"]
    assert cards[0]["is_public"] is True

    detail = api.get(f"/api/v1/discovery/bookable-venues/{venue['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["is_public"] is True

    users = [make_user(db_session) for _ in range(4)]
    _, lobby_format = make_format(db_session, team_size=2)
    lobby = Lobby(
        format_id=lobby_format.id,
        format_version=1,
        origin="manual",
        mode="casual",
        status="scheduled",
        court_preference="ANY",
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
    db_session.commit()

    booking = api.post(
        "/api/v1/bookings",
        headers=bearer(make_token(db_session, users[0])),
        json={
            "lobby_id": str(lobby.id),
            "organization_venue_id": venue["id"],
            "venue_space_id": space["id"],
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
        },
    )
    assert booking.status_code == 201, booking.text
    assert booking.json()["status"] == "PARTICIPANT_CONFIRMATION"


def test_deactivate_removes_from_discovery_and_preserves_rows(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)
    venue = create_venue(api, headers)
    space = add_space(api, headers, venue["id"], sport=sport)
    add_availability(api, headers, venue["id"], space["id"])
    publish_venue(api, headers, venue["id"])

    deactivated = api.post(
        f"/api/v1/admin/venues/{venue['id']}/deactivate",
        headers=headers,
        json={"reason": "manutenção"},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["status"] == "inactive"
    assert api.get("/api/v1/discovery/bookable-venues", headers=headers).json()["venues"] == []
    assert db_session.get(VenueSpace, UUID(space["id"])) is not None


def test_publication_requires_coordinates_and_price(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)

    no_coordinates = create_venue(api, headers, with_coordinates=False)
    blocked = api.post(
        f"/api/v1/admin/venues/{no_coordinates['id']}/activate",
        headers=headers,
        json={"reason": "tentativa sem coordenada"},
    )
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": {"code": "geocoding_required"}}

    venue = create_venue(api, headers)
    space = add_space(api, headers, venue["id"], sport=sport)
    add_availability(api, headers, venue["id"], space["id"])
    stored = db_session.get(VenueSpace, UUID(space["id"]))
    assert stored is not None
    stored.price_cents = None
    db_session.commit()

    no_price = api.post(
        f"/api/v1/admin/venues/{venue['id']}/activate",
        headers=headers,
        json={"reason": "tentativa sem preço"},
    )
    assert no_price.status_code == 422
    assert no_price.json() == {"detail": {"code": "pricing_not_configured"}}


def test_owner_and_operator_cannot_manage_public_venues(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)
    venue = create_venue(api, headers)
    add_space(api, headers, venue["id"], sport=sport)

    organization = Organization(name="Arena Privada")
    db_session.add(organization)
    db_session.flush()
    owner = make_user(db_session)
    operator = make_user(db_session)
    db_session.add_all(
        [
            OrganizationMembership(organization_id=organization.id, user_id=owner, role="OWNER"),
            OrganizationMembership(
                organization_id=organization.id, user_id=operator, role="OPERATOR"
            ),
        ]
    )
    db_session.commit()

    for user_id in (owner, operator):
        forbidden = api.patch(
            f"/api/v1/admin/venues/{venue['id']}",
            headers=bearer(make_token(db_session, user_id)),
            json={"name": "Não pode", "reason": "sem permissão"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": {"code": "forbidden"}}


def test_space_update_and_schedule_contract(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)
    venue = create_venue(api, headers)
    space = add_space(api, headers, venue["id"], sport=sport)
    add_availability(api, headers, venue["id"], space["id"])

    updated = api.patch(
        f"/api/v1/admin/venues/{venue['id']}/spaces/{space['id']}",
        headers=headers,
        json={"name": "Quadra Central", "price_cents": 15_000, "reason": "ajuste"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Quadra Central"
    assert updated.json()["price_cents"] == 15_000

    availability = api.get(
        f"/api/v1/admin/venues/{venue['id']}/availability",
        headers=headers,
        params={"space_id": space["id"]},
    )
    assert availability.status_code == 200, availability.text
    assert len(availability.json()) == 1
    assert availability.json()[0]["price_cents"] == 15_000

    detail = api.get(f"/api/v1/admin/venues/{venue['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["spaces_count"] == 1
    assert len(detail.json()["spaces"]) == 1
    assert detail.json()["spaces"][0]["price_cents"] == 15_000

    spaces = api.get(f"/api/v1/admin/venues/{venue['id']}/spaces", headers=headers)
    assert spaces.status_code == 200, spaces.text
    assert len(spaces.json()) == 1

    listed = api.get("/api/v1/admin/venues", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["venues"][0]["spaces_count"] == 1

    business_hour = api.post(
        f"/api/v1/admin/venues/{venue['id']}/business-hours",
        headers=headers,
        json={
            "weekday": 2,
            "opens_at": "08:00:00",
            "closes_at": "22:00:00",
            "reason": "expediente público",
        },
    )
    assert business_hour.status_code == 201, business_hour.text
    business_hours = api.get(f"/api/v1/admin/venues/{venue['id']}/business-hours", headers=headers)
    assert business_hours.status_code == 200
    assert len(business_hours.json()) == 1


class FakePostalCodeService:
    def resolve(self, postal_code: str, number: str | None = None) -> PostalCodeResult:
        del number
        return PostalCodeResult(
            location=PostalCodeLocation(
                cep="22000000",
                street="Avenida Atlântica",
                neighborhood="Copacabana",
                city="Rio de Janeiro",
                state="RJ",
                country="BR",
                lat=-22.97,
                lng=-43.18,
                precision="street",
                source="brasilapi",
            ),
            resolved_at=datetime.now(UTC),
        )


def test_admin_venue_geocodes_postal_code(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    api.app.dependency_overrides[get_postal_code_service] = lambda: FakePostalCodeService()

    response = api.post(
        "/api/v1/admin/venues",
        headers=headers,
        json={
            "name": "Quadra Geocodificada",
            "postal_code": "22000-000",
            "is_public": True,
            "reason": "cadastro por CEP",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["latitude"] == -22.97
    assert body["longitude"] == -43.18
    assert body["city"] == "Rio de Janeiro"
    assert body["state"] == "RJ"
    assert body["geocoding_source"] == "brasilapi"
    assert body["geocoding_precision"] == "street"


def test_admin_venue_reason_is_required(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    blank = api.post(
        "/api/v1/admin/venues",
        headers=headers,
        json={
            "name": "Sem motivo",
            "latitude": -22.9,
            "longitude": -43.2,
            "reason": "   ",
        },
    )
    assert blank.status_code == 422
    assert blank.json() == {"detail": {"code": "reason_required"}}


def test_admin_venue_list_filters_and_platform_org_is_hidden(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_catalog(api, headers)
    venue = create_venue(api, headers)
    add_space(api, headers, venue["id"], sport=sport)

    inactive = api.get("/api/v1/admin/venues?active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    assert inactive.json()["total"] == 1
    assert inactive.json()["venues"][0]["is_public"] is True

    platform_org = db_session.scalar(
        select(Organization).where(Organization.slug == "joga-publico")
    )
    assert platform_org is not None
    assert platform_org.is_platform is True
    assert db_session.get(User, admin_id) is not None
