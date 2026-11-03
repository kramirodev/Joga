"""Testes dos endpoints de perfil, disponibilidade, região e descoberta."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.profile import get_cep_resolver
from app.core.config import DEFAULT_TOKEN_HASH_SECRET, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.profile.cep import (
    CepLocation,
    CepProviderUnavailable,
    InvalidCep,
    normalize_cep,
)
from app.modules.profile.models import Sport, SportFormat, UserRegion, Venue

CENTER_LAT = -23.5503898
CENTER_LNG = -46.633081


class FakeCepResolver:
    def resolve(self, cep: str) -> CepLocation:
        normalized = normalize_cep(cep)
        if normalized == "99999999":
            raise CepProviderUnavailable("indisponível")
        if normalized == "00000000":
            raise InvalidCep("inválido")
        return CepLocation(
            cep=normalized,
            city="São Paulo",
            state="SP",
            lat=CENTER_LAT,
            lng=CENTER_LNG,
        )


@pytest.fixture
def api(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_cep_resolver] = lambda: FakeCepResolver()
    return client


def make_user_with_tokens(session: Session) -> str:
    user = User(status="active")
    session.add(user)
    session.flush()
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id)
    session.commit()
    return tokens.access_token


def seed_catalog(session: Session) -> tuple[SportFormat, SportFormat]:
    futebol = Sport(slug="futebol", name="Futebol")
    volei = Sport(slug="volei", name="Vôlei")
    session.add_all([futebol, volei])
    session.flush()
    futebol_5x5 = SportFormat(
        sport_id=futebol.id,
        slug="futebol-5x5",
        name="Futebol 5x5",
        team_size=5,
        total_participants=10,
        play_minutes=50,
        break_minutes=10,
        duration_minutes=60,
        version=1,
    )
    volei_6x6 = SportFormat(
        sport_id=volei.id,
        slug="volei-6x6",
        name="Vôlei 6x6",
        team_size=6,
        total_participants=12,
        play_minutes=60,
        break_minutes=0,
        duration_minutes=60,
        version=1,
    )
    session.add_all([futebol_5x5, volei_6x6])
    session.flush()
    return futebol_5x5, volei_6x6


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_cep_resolver_dependency_is_reusable() -> None:
    """Regressão: Settings não é hashable e não pode ser chave de cache."""
    first = get_cep_resolver(get_settings())
    second = get_cep_resolver(get_settings())

    assert first is second


def test_catalog_is_public(api: TestClient, db_session: Session) -> None:
    seed_catalog(db_session)

    response = api.get("/api/v1/sports")

    assert response.status_code == 200
    sports = response.json()["sports"]
    assert {item["slug"] for item in sports} == {"futebol", "volei"}
    futebol = next(item for item in sports if item["slug"] == "futebol")
    assert futebol["formats"][0]["duration_minutes"] == 60
    assert futebol["formats"][0]["play_minutes"] == 50
    assert futebol["formats"][0]["break_minutes"] == 10


def test_profile_requires_authentication(api: TestClient) -> None:
    assert api.get("/api/v1/me/profile").status_code == 401


def test_update_profile_and_sports(api: TestClient, db_session: Session) -> None:
    futebol, _ = seed_catalog(db_session)
    access = make_user_with_tokens(db_session)

    updated = api.put(
        "/api/v1/me/profile",
        headers=bearer(access),
        json={"display_name": "  Ana  ", "bio": "Jogo futebol"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Ana"
    assert updated.json()["bio"] == "Jogo futebol"

    sports = api.put(
        "/api/v1/me/sports",
        headers=bearer(access),
        json={
            "sports": [
                {
                    "format_id": str(futebol.id),
                    "level": "intermediate",
                    "court_preference": "PUBLIC_ONLY",
                }
            ]
        },
    )
    assert sports.status_code == 200
    assert sports.json()["sports"][0]["sport_slug"] == "futebol"
    assert sports.json()["sports"][0]["level"] == "intermediate"

    invalid = api.put(
        "/api/v1/me/sports",
        headers=bearer(access),
        json={
            "sports": [
                {
                    "format_id": "00000000-0000-0000-0000-000000000000",
                    "level": "beginner",
                }
            ]
        },
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": {"code": "invalid_sport_format"}}


def test_availability_rejects_overlap(api: TestClient, db_session: Session) -> None:
    access = make_user_with_tokens(db_session)
    valid = api.put(
        "/api/v1/me/availability",
        headers=bearer(access),
        json={
            "windows": [
                {"weekday": 1, "start_time": "18:00:00", "end_time": "20:00:00"},
                {"weekday": 1, "start_time": "20:00:00", "end_time": "22:00:00"},
            ]
        },
    )
    assert valid.status_code == 200
    assert len(valid.json()["availability"]) == 2

    overlap = api.put(
        "/api/v1/me/availability",
        headers=bearer(access),
        json={
            "windows": [
                {"weekday": 1, "start_time": "18:00:00", "end_time": "20:00:00"},
                {"weekday": 1, "start_time": "19:00:00", "end_time": "21:00:00"},
            ]
        },
    )
    assert overlap.status_code == 400
    assert overlap.json() == {"detail": {"code": "invalid_availability"}}


def test_availability_accepts_multiple_windows_per_day(
    api: TestClient,
    db_session: Session,
) -> None:
    """Agenda semanal: cada dia pode ter várias faixas, e dias diferem entre si."""
    access = make_user_with_tokens(db_session)

    response = api.put(
        "/api/v1/me/availability",
        headers=bearer(access),
        json={
            "windows": [
                {"weekday": 2, "start_time": "17:00:00", "end_time": "19:00:00"},
                {"weekday": 2, "start_time": "20:00:00", "end_time": "22:00:00"},
                {"weekday": 1, "start_time": "14:00:00", "end_time": "15:00:00"},
                {"weekday": 6, "start_time": "14:00:00", "end_time": "15:00:00"},
                {"weekday": 6, "start_time": "18:00:00", "end_time": "19:00:00"},
                {"weekday": 6, "start_time": "20:00:00", "end_time": "21:00:00"},
            ]
        },
    )

    assert response.status_code == 200
    windows = response.json()["availability"]
    assert len(windows) == 6
    assert len([item for item in windows if item["weekday"] == 2]) == 2
    assert len([item for item in windows if item["weekday"] == 6]) == 3


def test_region_by_cep_and_discovery(api: TestClient, db_session: Session) -> None:
    access = make_user_with_tokens(db_session)
    db_session.add_all(
        [
            Venue(
                name="Perto",
                kind="public",
                city="São Paulo",
                state="SP",
                lat=-23.551,
                lng=-46.634,
            ),
            Venue(
                name="Médio",
                kind="public",
                city="São Paulo",
                state="SP",
                lat=-23.7,
                lng=-46.8,
            ),
            Venue(
                name="Longe",
                kind="public",
                city="Rio de Janeiro",
                state="RJ",
                lat=-22.9,
                lng=-43.2,
            ),
        ]
    )
    db_session.flush()

    region = api.put(
        "/api/v1/me/region",
        headers=bearer(access),
        json={"cep": "01001-000", "radius_km": 10},
    )
    assert region.status_code == 200
    body = region.json()["region"]
    assert body["city"] == "São Paulo"
    assert body["state"] == "SP"
    assert body["radius_km"] == 10
    assert "lat" not in body and "lng" not in body

    stored = db_session.get(UserRegion, UUID(region.json()["user_id"]))
    assert stored is not None
    assert stored.center_lat == -23.55

    discovered = api.get(
        "/api/v1/discovery/venues",
        headers=bearer(access),
        params={"page": 1, "page_size": 20},
    )
    assert discovered.status_code == 200
    assert discovered.json()["total"] == 1
    assert discovered.json()["items"][0]["name"] == "Perto"

    wider = api.put(
        "/api/v1/me/region",
        headers=bearer(access),
        json={"cep": "01001000", "radius_km": 100},
    )
    assert wider.status_code == 200
    page_one = api.get(
        "/api/v1/discovery/venues",
        headers=bearer(access),
        params={"page": 1, "page_size": 1},
    )
    assert page_one.json()["total"] == 2
    assert len(page_one.json()["items"]) == 1


def test_region_rejects_invalid_cep_and_provider_error(
    api: TestClient,
    db_session: Session,
) -> None:
    access = make_user_with_tokens(db_session)

    invalid = api.put(
        "/api/v1/me/region",
        headers=bearer(access),
        json={"cep": "00000000"},
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": {"code": "invalid_cep"}}

    unavailable = api.put(
        "/api/v1/me/region",
        headers=bearer(access),
        json={"cep": "99999999"},
    )
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": {"code": "cep_unavailable"}}


def test_discovery_requires_region(api: TestClient, db_session: Session) -> None:
    access = make_user_with_tokens(db_session)

    response = api.get("/api/v1/discovery/venues", headers=bearer(access))

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "region_required"}}


def test_location_region_rounds_and_replaces_cep(
    api: TestClient,
    db_session: Session,
) -> None:
    access = make_user_with_tokens(db_session)
    api.put(
        "/api/v1/me/region",
        headers=bearer(access),
        json={"cep": "01001-000", "radius_km": 10},
    )

    response = api.put(
        "/api/v1/me/location",
        headers=bearer(access),
        json={"lat": CENTER_LAT, "lng": CENTER_LNG, "radius_km": 5},
    )

    assert response.status_code == 200
    region = response.json()["region"]
    assert region["source"] == "gps"
    assert region["cep"] is None
    assert region["city"] is None
    stored = db_session.get(UserRegion, UUID(response.json()["user_id"]))
    assert stored is not None
    assert stored.center_lat == -23.55
    assert stored.center_lng == -46.63
