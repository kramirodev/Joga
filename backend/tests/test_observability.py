"""Testes de request ID, headers e logs de acesso."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.core.observability import request_id_from


def test_request_id_is_generated_and_headers_are_set(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_safe_request_id_is_echoed(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "client-request-123"},
    )

    assert response.headers["X-Request-ID"] == "client-request-123"


def test_unsafe_request_id_is_replaced() -> None:
    assert request_id_from("with spaces") != "with spaces"
    assert request_id_from("x" * 65) != "x" * 65
    assert request_id_from("safe_request-1") == "safe_request-1"


def test_access_log_does_not_include_query_string(
    client: TestClient,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="joga.http")

    client.get("/api/v1/sports?token=secret-value")

    messages = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "joga.http"
    )
    assert "path=/api/v1/sports" in messages
    assert "secret-value" not in messages
