"""Docs interativas e schema OpenAPI só existem em ambiente local/teste."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def _client_for(environment: str) -> TestClient:
    settings = get_settings().model_copy(update={"environment": environment})
    return TestClient(create_app(settings))


def test_docs_and_openapi_are_disabled_outside_local() -> None:
    with _client_for("demo") as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_docs_and_openapi_are_available_in_local(client: TestClient) -> None:
    assert client.app.state.settings.environment == "test"

    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_openapi_schema_still_builds_without_public_url() -> None:
    app = create_app(get_settings().model_copy(update={"environment": "demo"}))

    assert app.openapi()["info"]["title"] == "JOGA API"
