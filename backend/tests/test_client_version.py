"""Testes do gate de versão mínima do app mobile (ADR 0051)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.core.versioning import parse_version
from app.main import create_app

OLD = "1.0.0"
MIN = "1.0.1"


def gate_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "app_version_gate_enabled": True,
        "min_app_version": MIN,
        "latest_app_version": MIN,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_parse_version() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version(" 10.0.4 ") == (10, 0, 4)
    assert parse_version("1.2") is None
    assert parse_version("1.2.3-beta") is None
    assert parse_version("") is None
    assert parse_version(None) is None


def test_gate_disabled_allows_old_mobile() -> None:
    with TestClient(create_app(gate_settings(app_version_gate_enabled=False))) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "mobile", "X-App-Version": OLD},
        )
    assert response.status_code == 404


def test_gate_blocks_old_mobile_version() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "mobile", "X-App-Version": OLD},
        )
    assert response.status_code == 426
    detail = response.json()["detail"]
    assert detail["code"] == "app_update_required"
    assert detail["min_supported_version"] == MIN
    assert detail["latest_version"] == MIN
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"


def test_gate_allows_minimum_and_newer_versions() -> None:
    with TestClient(create_app(gate_settings())) as client:
        minimum = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "mobile", "X-App-Version": MIN},
        )
        newer = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "mobile", "X-App-Version": "2.0.0"},
        )
    assert minimum.status_code == 404
    assert newer.status_code == 404


def test_gate_blocks_mobile_without_version() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get("/api/v1/_version_probe", headers={"X-Client": "mobile"})
    assert response.status_code == 426
    assert response.json()["detail"]["code"] == "app_update_required"


def test_gate_blocks_old_mobile_by_user_agent() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"User-Agent": "okhttp/4.12.0"},
        )
    assert response.status_code == 426
    assert response.json()["detail"]["code"] == "app_update_required"


def test_gate_allows_browser_without_headers() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"User-Agent": "Mozilla/5.0"},
        )
    assert response.status_code == 404


def test_gate_allows_web_client() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "web", "X-App-Version": "0.0.1"},
        )
    assert response.status_code == 404


def test_gate_blocks_unknown_client() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "robot", "X-App-Version": MIN},
        )
    assert response.status_code == 426
    assert response.json()["detail"]["code"] == "unsupported_client"


def test_gate_blocks_invalid_version() -> None:
    with TestClient(create_app(gate_settings())) as client:
        response = client.get(
            "/api/v1/_version_probe",
            headers={"X-Client": "mobile", "X-App-Version": "1.0"},
        )
    assert response.status_code == 426


def test_health_and_app_config_are_exempt() -> None:
    with TestClient(create_app(gate_settings())) as client:
        health = client.get("/api/v1/health/live", headers={"User-Agent": "okhttp/4.12.0"})
        config = client.get(
            "/api/v1/app-config",
            headers={"User-Agent": "okhttp/4.12.0", "X-Client": "mobile"},
        )
    assert health.status_code == 200
    assert config.status_code == 200


def test_app_config_reports_update_required() -> None:
    with TestClient(create_app(gate_settings())) as client:
        old = client.get(
            "/api/v1/app-config",
            headers={"X-Client": "mobile", "X-App-Version": OLD},
        )
        current = client.get(
            "/api/v1/app-config",
            headers={"X-Client": "mobile", "X-App-Version": MIN},
        )
        web = client.get("/api/v1/app-config", headers={"X-Client": "web"})
    assert old.json()["update_required"] is True
    assert current.json()["update_required"] is False
    assert web.json()["update_required"] is False
    assert old.json()["min_supported_version"] == MIN
    assert old.json()["version_gate_enabled"] is True


def test_websocket_gate_closes_old_mobile() -> None:
    with TestClient(create_app(gate_settings())) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/v1/ws",
                headers={
                    "X-Client": "mobile",
                    "X-App-Version": OLD,
                    "Authorization": "Bearer fake-token",
                },
            ) as socket:
                socket.receive_json()
    assert error.value.code == 4403


def test_websocket_gate_allows_current_mobile_to_auth() -> None:
    with TestClient(create_app(gate_settings())) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/v1/ws",
                headers={
                    "X-Client": "mobile",
                    "X-App-Version": MIN,
                    "Authorization": "Bearer fake-token",
                },
            ) as socket:
                socket.receive_json()
    assert error.value.code == 4401


def test_app_version_policy_rejects_min_above_latest() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            min_app_version="2.0.0",
            latest_app_version="1.0.0",
        )


def test_app_version_policy_rejects_non_https_update_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_update_url="http://example.com/update")
