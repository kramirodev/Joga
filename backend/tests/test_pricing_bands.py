"""Testes de faixas de preço e reajuste (Fase 14D.1, ADR 0042 §3/§9)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.matchmaking.models import Lobby
from app.modules.profile.models import Sport, SportFormat
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_space(api: TestClient, db_session: Session) -> tuple[str, str, str, str]:
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    org = api.post("/api/v1/organizations", headers=bearer(token), json={"name": "Arena Faixa"})
    assert org.status_code == 201, org.text
    organization_id = org.json()["id"]
    venue = api.post(
        f"/api/v1/organizations/{organization_id}/venues",
        headers=bearer(token),
        json={
            "name": "Arena Faixa Centro",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text
    base = f"/api/v1/organizations/{organization_id}/venues/{venue.json()['id']}"
    space = api.post(
        f"{base}/spaces",
        headers=bearer(token),
        json={"name": "Quadra 1", "is_covered": True},
    )
    assert space.status_code == 201, space.text
    assert space.json()["is_covered"] is True
    return token, base, space.json()["id"], organization_id


def create_availability(
    api: TestClient,
    token: str,
    base: str,
    space_id: str,
    *,
    weekday: int = 2,
    start_time: str = "19:00:00",
    end_time: str = "20:00:00",
    price_cents: int = 12_000,
) -> dict:
    response = api.post(
        f"{base}/spaces/{space_id}/availability",
        headers=bearer(token),
        json={
            "weekday": weekday,
            "start_time": start_time,
            "end_time": end_time,
            "price_cents": price_cents,
            "slot_minutes": 60,
        },
    )
    return {"status": response.status_code, "body": response.json()}


def band_labels(api: TestClient, token: str) -> dict[str, str]:
    response = api.get("/api/v1/pricing/bands", headers=bearer(token))
    assert response.status_code == 200, response.text
    return {item["code"]: item["label"] for item in response.json()["bands"]}


def test_band_is_resolved_by_price_ceiling(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    token, base, space_id, _ = setup_space(api, db_session)
    labels = band_labels(api, token)
    assert labels["premium"] == "Premium"

    cheap = create_availability(api, token, base, space_id, weekday=2, price_cents=12_000)
    assert cheap["status"] == 201, cheap["body"]
    assert cheap["body"]["band_id"] is not None

    other = create_availability(
        api, token, base, space_id, weekday=3, start_time="08:00:00",
        end_time="09:00:00", price_cents=12_100,
    )
    assert other["status"] == 201, other["body"]
    assert other["body"]["band_id"] != cheap["body"]["band_id"]

    top = create_availability(
        api, token, base, space_id, weekday=4, start_time="08:00:00",
        end_time="09:00:00", price_cents=30_000,
    )
    assert top["status"] == 201, top["body"]


def test_price_above_last_ceiling_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    token, base, space_id, _ = setup_space(api, db_session)

    response = create_availability(api, token, base, space_id, price_cents=30_001)
    assert response["status"] == 422, response["body"]
    assert response["body"]["detail"]["code"] == "price_above_band"


def test_price_change_applies_only_to_new_bookings(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    token, base, space_id, organization_id = setup_space(api, db_session)
    created = create_availability(api, token, base, space_id)
    assert created["status"] == 201, created["body"]
    availability_id = created["body"]["id"]

    sport = Sport(slug="futebol-faixa", name="Futebol")
    db_session.add(sport)
    db_session.flush()
    fmt = SportFormat(
        sport_id=sport.id,
        slug="fut5-faixa",
        name="Futebol 5",
        team_size=5,
        total_participants=10,
        play_minutes=60,
        break_minutes=0,
        duration_minutes=60,
    )
    db_session.add(fmt)
    db_session.flush()

    start = datetime.now(UTC) + timedelta(days=7)
    while start.isoweekday() != 2:
        start += timedelta(days=1)
    start = start.replace(hour=19, minute=0, second=0, microsecond=0)

    lobby = Lobby(
        format_id=fmt.id,
        format_version=1,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(minutes=60),
        duration_minutes=60,
        center_lat=-22.9,
        center_lng=-43.2,
        radius_km=10,
        algorithm_version="test",
    )
    db_session.add(lobby)
    db_session.flush()
    db_session.add(
        Booking(
            lobby_id=lobby.id,
            organization_id=uuid.UUID(organization_id),
            organization_venue_id=uuid.UUID(base.split("/venues/")[1]),
            venue_space_id=uuid.UUID(space_id),
            status="CONFIRMED",
            starts_at=start,
            ends_at=start + timedelta(minutes=60),
            price_cents=12_000,
            seats=10,
            policy_version="v1",
            cancellation_policy="full_refund_until_confirmed",
            payment_version=1,
        )
    )
    db_session.flush()

    response = api.patch(
        f"{base}/spaces/{space_id}/availability/{availability_id}",
        headers=bearer(token),
        json={"price_cents": 13_000},
    )
    assert response.status_code == 200, response.text

    # A reserva já feita mantém o preço com que foi criada.
    booking = db_session.query(Booking).one()
    db_session.refresh(booking)
    assert booking.price_cents == 12_000
    # A reserva nova usaria a faixa nova (R$ 130 cabe em "Econômica noite").
    assert response.json()["band_id"] != created["body"]["band_id"]
