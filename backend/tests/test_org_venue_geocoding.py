"""Criação de quadra por CEP no endpoint de organização (sem rede real)."""

from __future__ import annotations

import urllib.request

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.api.v1.geo import get_postal_code_resolver
from app.core.config import Settings, get_settings
from app.modules.geo.service import PostalCodeResolver
from app.modules.profile.cep import (
    CepNotFound,
    CepTimeout,
    PostalCodeLocation,
)
from tests.cnpj_helpers import (
    PARTNER_CPF,
    FakeCnpjLookup,
    api_with_lookup,
    make_cnpj_user,
    next_test_cnpj,
)
from tests.helpers_results import make_token


class FakeResolver:
    """Resolvedor controlado; conta chamadas para provar que não há rede."""

    def __init__(self, location: PostalCodeLocation | None = None) -> None:
        self.calls = 0
        self.error: Exception | None = None
        self.location = location

    def resolve_postal_code(self, cep: str) -> PostalCodeLocation:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.location is not None:
            return self.location
        return PostalCodeLocation(
            cep=cep,
            street="Rua Barão de Mesquita",
            neighborhood="Tijuca",
            city="Rio de Janeiro",
            state="RJ",
            country="BR",
            lat=-22.9234,
            lng=-43.2456,
            precision="street",
            source="brasilapi",
        )


def api_client(
    client: TestClient,
    db_session: Session,
    resolver: PostalCodeResolver,
    *,
    settings: Settings | None = None,
) -> TestClient:
    client = api_with_lookup(client, db_session, FakeCnpjLookup())
    client.app.dependency_overrides[get_postal_code_resolver] = lambda: resolver
    if settings is not None:
        client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_org(api: TestClient, db_session: Session) -> tuple[str, str]:
    owner = make_cnpj_user(db_session)
    token = make_token(db_session, owner)
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json={"name": "Arena CEP", "cnpj": next_test_cnpj(), "cpf": PARTNER_CPF},
    )
    assert response.status_code == 201, response.text
    return token, response.json()["id"]


def post_venue(
    api: TestClient,
    token: str,
    organization_id: str,
    payload: dict[str, object],
) -> Response:
    return api.post(
        f"/api/v1/organizations/{organization_id}/venues",
        headers=bearer(token),
        json=payload,
    )


def test_venue_created_with_postal_code_only(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    def forbidden_urlopen(*args: object, **kwargs: object) -> None:
        raise AssertionError("chamada de rede real durante o teste")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden_urlopen)

    response = post_venue(
        api, token, organization_id, {"name": "Arena CEP", "postal_code": "20541-004"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["latitude"] == pytest.approx(-22.9234)
    assert body["longitude"] == pytest.approx(-43.2456)
    assert body["city"] == "Rio de Janeiro"
    assert body["state"] == "RJ"
    assert body["postal_code"] == "20541004"
    assert body["geocoding_source"] == "brasilapi"
    assert body["geocoding_precision"] == "street"
    assert body["geocoded_at"] is not None
    assert resolver.calls == 1


def test_postal_code_without_coordinates_is_unresolved(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver(
        PostalCodeLocation(
            cep="20541004",
            street=None,
            neighborhood=None,
            city="Rio de Janeiro",
            state="RJ",
            country="BR",
            lat=None,
            lng=None,
            precision="unresolved",
            source="brasilapi",
        )
    )
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api, token, organization_id, {"name": "Arena CEP", "postal_code": "20541004"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "geocoding_unresolved"}}
    assert resolver.calls == 1
    listed = api.get(
        f"/api/v1/organizations/{organization_id}/venues",
        headers=bearer(token),
    )
    assert listed.json()["venues"] == []


def test_postal_code_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    resolver.error = CepNotFound("não encontrado")
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api, token, organization_id, {"name": "Arena CEP", "postal_code": "99999999"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "postal_code_not_found"}}


def test_postal_code_timeout(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    resolver.error = CepTimeout("timeout")
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api, token, organization_id, {"name": "Arena CEP", "postal_code": "20541004"}
    )

    assert response.status_code == 504
    assert response.json() == {"detail": {"code": "geocoding_timeout"}}


def test_malformed_postal_code(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(api, token, organization_id, {"name": "Arena CEP", "postal_code": "123"})

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_postal_code"}}
    assert resolver.calls == 0


def test_coordinates_out_of_range_are_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session, FakeResolver())
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api,
        token,
        organization_id,
        {"name": "Arena CEP", "latitude": 91.0, "longitude": -43.2},
    )

    assert response.status_code == 422


def test_manual_venue_without_postal_code_still_works(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api,
        token,
        organization_id,
        {
            "name": "Arena Manual",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["geocoding_source"] is None
    assert body["geocoding_precision"] == "manual"
    assert body["geocoded_at"] is None
    assert resolver.calls == 0


def test_missing_coordinates_without_postal_code_are_required(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token, organization_id = create_org(api, db_session)

    response = post_venue(
        api,
        token,
        organization_id,
        {"name": "Arena Sem Endereço", "city": "Rio de Janeiro", "state": "RJ"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "geocoding_required"}}
    assert resolver.calls == 0


def test_venue_geocoding_rate_limit(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    settings = get_settings().model_copy(update={"geo_rate_limit_per_minute": 1})
    api = api_client(client, db_session, resolver, settings=settings)
    token, organization_id = create_org(api, db_session)

    first = post_venue(
        api, token, organization_id, {"name": "Arena CEP", "postal_code": "20541004"}
    )
    second = post_venue(
        api, token, organization_id, {"name": "Arena CEP 2", "postal_code": "20541004"}
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 429
    assert second.json() == {"detail": {"code": "rate_limited"}}
    assert second.headers["retry-after"]
    assert resolver.calls == 1
