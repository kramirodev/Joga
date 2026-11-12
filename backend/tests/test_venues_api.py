"""Testes HTTP de quadras, agenda, bloqueios e fotos (Fase 12A)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.profile.models import Sport
from app.modules.profile.models import Venue as DiscoveryVenue
from app.modules.venues.storage import LocalPhotoStorage, get_photo_storage
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session, media_root: Path) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    storage = LocalPhotoStorage(media_root)
    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_photo_storage] = lambda: storage
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_organization(api: TestClient, token: str, name: str) -> dict:
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_venue(api: TestClient, token: str, organization_id: str, name: str) -> dict:
    response = api.post(
        f"/api/v1/organizations/{organization_id}/venues",
        headers=bearer(token),
        json={
            "name": name,
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_member(
    api: TestClient,
    token: str,
    organization_id: str,
    user_id: uuid.UUID,
    role: str,
) -> None:
    response = api.post(
        f"/api/v1/organizations/{organization_id}/members",
        headers=bearer(token),
        json={"user_id": str(user_id), "role": role},
    )
    assert response.status_code == 201, response.text


def setup_tenant(
    api: TestClient,
    db_session: Session,
    *,
    name: str = "Arena Teste",
) -> tuple[uuid.UUID, str, dict, dict]:
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    organization = create_organization(api, token, name)
    venue = create_venue(api, token, organization["id"], f"{name} Centro")
    return user_id, token, organization, venue


def base_path(organization: dict, venue: dict) -> str:
    return f"/api/v1/organizations/{organization['id']}/venues/{venue['id']}"


def image_bytes(size: tuple[int, int] = (800, 600), image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (30, 120, 210)).save(output, format=image_format)
    return output.getvalue()


def seed_sport(db_session: Session, slug: str = "futebol") -> Sport:
    sport = Sport(slug=slug, name=slug.title())
    db_session.add(sport)
    db_session.flush()
    return sport


def create_space(api: TestClient, token: str, base: str, name: str = "Quadra 1") -> dict:
    response = api.post(
        f"{base}/spaces",
        headers=bearer(token),
        json={"name": name, "description": "Quadra coberta"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_venue_can_link_only_private_discovery_venue(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, token, organization, _ = setup_tenant(api, db_session)
    private = DiscoveryVenue(
        name="Arena Descoberta",
        kind="private",
        city="Rio de Janeiro",
        state="RJ",
        lat=-22.9,
        lng=-43.2,
    )
    public = DiscoveryVenue(
        name="Praça Pública",
        kind="public",
        city="Rio de Janeiro",
        state="RJ",
        lat=-22.91,
        lng=-43.21,
    )
    db_session.add_all([private, public])
    db_session.flush()

    created = api.post(
        f"/api/v1/organizations/{organization['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Arena Vinculada",
            "venue_id": str(private.id),
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["venue_id"] == str(private.id)

    public_link = api.post(
        f"/api/v1/organizations/{organization['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Arena Pública",
            "venue_id": str(public.id),
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert public_link.status_code == 422

    duplicate = api.post(
        f"/api/v1/organizations/{organization['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Arena Duplicada",
            "venue_id": str(private.id),
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert duplicate.status_code == 422

    unlinked = api.patch(
        f"/api/v1/organizations/{organization['id']}/venues/{created.json()['id']}",
        headers=bearer(token),
        json={"venue_id": None},
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["venue_id"] is None


def test_space_crud_sports_and_audit(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, token, organization, venue = setup_tenant(api, db_session)
    sport = seed_sport(db_session)
    base = base_path(organization, venue)

    space = create_space(api, token, base)
    assert space["sports"] == []

    listed = api.get(f"{base}/spaces", headers=bearer(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["spaces"]] == [space["id"]]

    updated = api.patch(
        f"{base}/spaces/{space['id']}",
        headers=bearer(token),
        json={"name": "Quadra Central", "status": "inactive"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Quadra Central"
    assert updated.json()["status"] == "inactive"

    sports = api.put(
        f"{base}/spaces/{space['id']}/sports",
        headers=bearer(token),
        json={"sport_ids": [str(sport.id)]},
    )
    assert sports.status_code == 200, sports.text
    assert [item["slug"] for item in sports.json()] == ["futebol"]

    fetched = api.get(f"{base}/spaces/{space['id']}", headers=bearer(token))
    assert fetched.status_code == 200
    assert [item["id"] for item in fetched.json()["sports"]] == [str(sport.id)]

    removed = api.delete(f"{base}/spaces/{space['id']}", headers=bearer(token))
    assert removed.status_code == 204
    assert api.get(f"{base}/spaces/{space['id']}", headers=bearer(token)).status_code == 404

    audit = api.get(f"/api/v1/organizations/{organization['id']}/audit", headers=bearer(token))
    actions = {item["action"] for item in audit.json()["audit"]}
    assert "venue_space.created" in actions
    assert "venue_space.sports_replaced" in actions
    assert "venue_space.deleted" in actions


def test_cross_organization_access_is_denied(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, first_token, first_org, first_venue = setup_tenant(api, db_session, name="Arena A")
    second_user = make_user(db_session)
    second_token = make_token(db_session, second_user)
    second_org = create_organization(api, second_token, "Arena B")
    second_venue = create_venue(api, second_token, second_org["id"], "Arena B Centro")

    first_base = base_path(first_org, first_venue)
    second_base = base_path(second_org, second_venue)
    first_space = create_space(api, first_token, first_base)

    assert api.get(f"{first_base}/spaces", headers=bearer(second_token)).status_code == 404

    cross_venue = api.get(
        f"/api/v1/organizations/{first_org['id']}/venues/{second_venue['id']}/spaces",
        headers=bearer(first_token),
    )
    assert cross_venue.status_code == 404
    assert cross_venue.json()["detail"]["code"] == "venue_not_found"

    cross_space = api.patch(
        f"{second_base}/spaces/{first_space['id']}",
        headers=bearer(second_token),
        json={"name": "Invasão"},
    )
    assert cross_space.status_code == 404

    upload = api.post(
        f"{first_base}/photos",
        headers=bearer(second_token),
        files={"file": ("quadra.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 404


def test_operator_can_manage_spaces_but_cannot_review_photos(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, owner_token, organization, venue = setup_tenant(api, db_session)
    operator = make_user(db_session)
    operator_token = make_token(db_session, operator)
    add_member(api, owner_token, organization["id"], operator, "OPERATOR")
    base = base_path(organization, venue)

    space = create_space(api, operator_token, base)
    assert space["name"] == "Quadra 1"

    uploaded = api.post(
        f"{base}/photos",
        headers=bearer(operator_token),
        files={"file": ("quadra.png", image_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["status"] == "PENDING"
    assert uploaded.json()["can_review"] is False

    review = api.post(
        f"{base}/photos/{uploaded.json()['id']}/review",
        headers=bearer(operator_token),
        json={"decision": "APPROVED"},
    )
    assert review.status_code == 403
    assert review.json()["detail"]["code"] == "review_not_allowed"


def test_availability_overlap_and_validation(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, token, organization, venue = setup_tenant(api, db_session)
    base = base_path(organization, venue)
    space = create_space(api, token, base)

    created = api.post(
        f"{base}/spaces/{space['id']}/availability",
        headers=bearer(token),
        json={
            "weekday": 1,
            "start_time": "18:00:00",
            "end_time": "22:00:00",
            "price_cents": 12000,
            "slot_minutes": 60,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["price_cents"] == 12000

    overlap = api.post(
        f"{base}/spaces/{space['id']}/availability",
        headers=bearer(token),
        json={
            "weekday": 1,
            "start_time": "21:00:00",
            "end_time": "23:00:00",
            "price_cents": 12000,
            "slot_minutes": 60,
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["detail"]["code"] == "availability_overlap"

    adjacent = api.post(
        f"{base}/spaces/{space['id']}/availability",
        headers=bearer(token),
        json={
            "weekday": 1,
            "start_time": "22:00:00",
            "end_time": "23:00:00",
            "price_cents": 10000,
            "slot_minutes": 60,
        },
    )
    assert adjacent.status_code == 201, adjacent.text

    invalid = api.post(
        f"{base}/spaces/{space['id']}/availability",
        headers=bearer(token),
        json={
            "weekday": 2,
            "start_time": "22:00:00",
            "end_time": "18:00:00",
            "price_cents": 10000,
            "slot_minutes": 60,
        },
    )
    assert invalid.status_code == 422

    listed = api.get(f"{base}/spaces/{space['id']}/availability", headers=bearer(token))
    assert listed.status_code == 200
    assert len(listed.json()["availability"]) == 2

    deleted = api.delete(
        f"{base}/spaces/{space['id']}/availability/{created.json()['id']}",
        headers=bearer(token),
    )
    assert deleted.status_code == 204


def test_blackouts_are_timezone_aware_and_cannot_overlap(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, token, organization, venue = setup_tenant(api, db_session)
    base = base_path(organization, venue)
    space = create_space(api, token, base)

    created = api.post(
        f"{base}/spaces/{space['id']}/blackouts",
        headers=bearer(token),
        json={
            "starts_at": "2026-12-01T18:00:00Z",
            "ends_at": "2026-12-01T20:00:00Z",
            "reason": "Reserva externa",
            "external_reference": "externa-123",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["external_reference"] == "externa-123"

    overlap = api.post(
        f"{base}/spaces/{space['id']}/blackouts",
        headers=bearer(token),
        json={
            "starts_at": "2026-12-01T19:00:00Z",
            "ends_at": "2026-12-01T21:00:00Z",
            "reason": "Outra reserva",
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["detail"]["code"] == "blackout_overlap"

    naive = api.post(
        f"{base}/spaces/{space['id']}/blackouts",
        headers=bearer(token),
        json={
            "starts_at": "2026-12-02T18:00:00",
            "ends_at": "2026-12-02T20:00:00",
            "reason": "Sem fuso",
        },
    )
    assert naive.status_code == 422

    listed = api.get(f"{base}/spaces/{space['id']}/blackouts", headers=bearer(token))
    assert len(listed.json()["blackouts"]) == 1

    deleted = api.delete(
        f"{base}/spaces/{space['id']}/blackouts/{created.json()['id']}",
        headers=bearer(token),
    )
    assert deleted.status_code == 204


def test_photo_upload_review_serving_and_removal(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, token, organization, venue = setup_tenant(api, db_session)
    base = base_path(organization, venue)
    space = create_space(api, token, base)

    uploaded = api.post(
        f"{base}/photos",
        headers=bearer(token),
        files={"file": ("quadra.png", image_bytes(), "image/png")},
        data={"caption": "Quadra coberta", "space_id": space["id"]},
    )
    assert uploaded.status_code == 201, uploaded.text
    photo = uploaded.json()
    assert photo["status"] == "PENDING"
    assert photo["can_review"] is True
    assert photo["space_id"] == space["id"]
    assert photo["content_url"].endswith(f"/photos/{photo['id']}/content")

    listed = api.get(f"{base}/photos", headers=bearer(token))
    assert listed.status_code == 200
    assert listed.json()["can_review"] is True
    assert [item["id"] for item in listed.json()["photos"]] == [photo["id"]]

    content = api.get(f"{base}/photos/{photo['id']}/content", headers=bearer(token))
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/jpeg"
    assert content.headers["cache-control"] == "no-store"
    assert content.content.startswith(b"\xff\xd8")

    approved = api.post(
        f"{base}/photos/{photo['id']}/review",
        headers=bearer(token),
        json={"decision": "APPROVED"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    rejected_without_reason = api.post(
        f"{base}/photos/{photo['id']}/review",
        headers=bearer(token),
        json={"decision": "REJECTED"},
    )
    assert rejected_without_reason.status_code == 422

    rejected = api.post(
        f"{base}/photos/{photo['id']}/review",
        headers=bearer(token),
        json={"decision": "REJECTED", "reason": "Pessoa identificável em primeiro plano"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    invalid = api.post(
        f"{base}/photos",
        headers=bearer(token),
        files={"file": ("quadra.png", b"isto nao e imagem", "image/png")},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_photo"

    removed = api.delete(f"{base}/photos/{photo['id']}", headers=bearer(token))
    assert removed.status_code == 204
    assert api.get(f"{base}/photos/{photo['id']}/content", headers=bearer(token)).status_code == 404

    remaining = api.get(f"{base}/photos", headers=bearer(token))
    assert remaining.json()["photos"] == []


def test_photo_requires_member_of_the_same_venue(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    api = api_client(client, db_session, tmp_path)
    _, first_token, first_org, first_venue = setup_tenant(api, db_session, name="Arena A")
    second_user = make_user(db_session)
    second_token = make_token(db_session, second_user)
    second_org = create_organization(api, second_token, "Arena B")
    second_venue = create_venue(api, second_token, second_org["id"], "Arena B Centro")

    base = base_path(first_org, first_venue)
    uploaded = api.post(
        f"{base}/photos",
        headers=bearer(first_token),
        files={"file": ("quadra.png", image_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201

    other_base = base_path(second_org, second_venue)
    other_content = api.get(
        f"{other_base}/photos/{uploaded.json()['id']}/content",
        headers=bearer(second_token),
    )
    assert other_content.status_code == 404
