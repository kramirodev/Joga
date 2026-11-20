"""Testes da allowlist de Host e do proto encaminhado pelo proxy."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import Settings
from app.main import create_app


def test_forged_host_is_rejected_without_redirect(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health/live/",
        headers={"Host": "evil.example"},
    )

    assert response.status_code in {400, 421}
    assert "location" not in response.headers
    assert "evil.example" not in response.headers.get("location", "")
    # A rejeição passa pela observabilidade: headers padrão continuam presentes.
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("host", ["testserver", "localhost:8000", "127.0.0.1:8000"])
def test_allowed_host_is_served(client: TestClient, host: str) -> None:
    response = client.get("/api/v1/health/live", headers={"Host": host})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_forwarded_proto_reaches_redirect_behind_proxy() -> None:
    app = create_app()
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=["testclient"])

    with TestClient(proxied) as proxied_client:
        response = proxied_client.get(
            "/api/v1/health/live/",
            headers={"X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["Location"] == "https://testserver/api/v1/health/live"


def test_redirect_is_http_without_proxy_headers() -> None:
    """Sensibilidade do teste: sem o proto do proxy o redirect volta a http."""

    with TestClient(create_app()) as plain_client:
        response = plain_client.get("/api/v1/health/live/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["Location"] == "http://testserver/api/v1/health/live"


def test_www_style_allowlist_never_redirects_attacker_host() -> None:
    settings = Settings(environment="local", trusted_hosts="www.example.com")

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"Host": "example.com"},
        )

    assert response.status_code in {400, 421}
    assert "location" not in response.headers


def test_render_hostname_and_configured_hosts_are_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "joga-demo.onrender.com")
    settings = Settings(environment="local", trusted_hosts="api.example.com")

    assert settings.trusted_host_list == [
        "localhost",
        "127.0.0.1",
        "testserver",
        "joga-demo.onrender.com",
        "api.example.com",
    ]

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"Host": "joga-demo.onrender.com"},
        )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "value",
    ["*", "*.example.com", "https://example.com", "example.com:443", "example.com/api"],
)
def test_wildcard_and_non_host_entries_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(environment="local", trusted_hosts=value)
