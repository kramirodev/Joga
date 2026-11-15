"""Testes do endpoint de CEP para estabelecimentos (Fase 1)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.geo import get_postal_code_resolver
from app.infrastructure.database.dependency import get_session
from app.modules.geo.service import PostalCodeResolver
from app.modules.profile.cep import (
    CepNotFound,
    CepProviderUnavailable,
    CepTimeout,
    PostalCodeLocation,
)
from tests.helpers_results import make_token, make_user


def api_client(
    client: TestClient,
    db_session: Session,
    resolver: PostalCodeResolver,
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_postal_code_resolver] = lambda: resolver
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class FakeResolver:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    def resolve_postal_code(self, cep: str) -> PostalCodeLocation:
        self.calls += 1
        if self.error is not None:
            raise self.error
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


def test_postal_code_requires_authentication(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session, FakeResolver())
    response = api.get("/api/v1/geo/postal-codes/20541004")
    assert response.status_code == 401


def test_postal_code_accepts_hyphen_and_returns_contract(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token = make_token(db_session, make_user(db_session))

    response = api.get(
        "/api/v1/geo/postal-codes/20541-004?number=1200",
        headers=bearer(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["postal_code"] == "20541004"
    assert body["street"] == "Rua Barão de Mesquita"
    assert body["neighborhood"] == "Tijuca"
    assert body["city"] == "Rio de Janeiro"
    assert body["state"] == "RJ"
    assert body["country"] == "BR"
    assert body["latitude"] == -22.9234
    assert body["longitude"] == -43.2456
    assert body["precision"] == "street"
    assert body["source"] == "brasilapi"
    assert body["resolved_at"]
    assert resolver.calls == 1


def test_postal_code_cache_avoids_second_provider_call(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token = make_token(db_session, make_user(db_session))

    first = api.get("/api/v1/geo/postal-codes/20541004", headers=bearer(token))
    second = api.get("/api/v1/geo/postal-codes/20541004", headers=bearer(token))
    with_number = api.get(
        "/api/v1/geo/postal-codes/20541004?number=1200",
        headers=bearer(token),
    )
    same_number = api.get(
        "/api/v1/geo/postal-codes/20541004?number=1200",
        headers=bearer(token),
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert with_number.status_code == 200, with_number.text
    assert same_number.status_code == 200, same_number.text
    assert resolver.calls == 2
    assert first.json()["resolved_at"] == second.json()["resolved_at"]
    assert with_number.json()["resolved_at"] == same_number.json()["resolved_at"]


def test_postal_code_errors_map_to_stable_codes(
    client: TestClient,
    db_session: Session,
) -> None:
    resolver = FakeResolver()
    api = api_client(client, db_session, resolver)
    token = make_token(db_session, make_user(db_session))
    headers = bearer(token)

    invalid = api.get("/api/v1/geo/postal-codes/123", headers=headers)
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "invalid_postal_code"

    resolver.error = CepNotFound("não encontrado")
    missing = api.get("/api/v1/geo/postal-codes/99999999", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "postal_code_not_found"

    resolver.error = CepTimeout("timeout")
    timeout = api.get("/api/v1/geo/postal-codes/20541004", headers=headers)
    assert timeout.status_code == 504
    assert timeout.json()["detail"]["code"] == "geocoding_timeout"

    resolver.error = CepProviderUnavailable("indisponível")
    unavailable = api.get("/api/v1/geo/postal-codes/20541004", headers=headers)
    assert unavailable.status_code == 502
    assert unavailable.json()["detail"]["code"] == "geocoding_provider_error"


def test_postal_code_unresolved_returns_null_coordinates(
    client: TestClient,
    db_session: Session,
) -> None:
    class UnresolvedResolver(FakeResolver):
        def resolve_postal_code(self, cep: str) -> PostalCodeLocation:
            self.calls += 1
            return PostalCodeLocation(
                cep=cep,
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

    api = api_client(client, db_session, UnresolvedResolver())
    token = make_token(db_session, make_user(db_session))

    response = api.get("/api/v1/geo/postal-codes/20541004", headers=bearer(token))
    assert response.status_code == 200, response.text
    assert response.json()["latitude"] is None
    assert response.json()["longitude"] is None
    assert response.json()["precision"] == "unresolved"


def test_postal_code_rate_limit(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session, FakeResolver())
    token = make_token(db_session, make_user(db_session))

    for _index in range(30):
        response = api.get("/api/v1/geo/postal-codes/20541004", headers=bearer(token))
        assert response.status_code == 200, response.text

    limited = api.get("/api/v1/geo/postal-codes/20541004", headers=bearer(token))
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limited"
    assert limited.headers["retry-after"]
