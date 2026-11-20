"""Testes de request ID, headers e logs de acesso."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import Request
from fastapi.testclient import TestClient

from app.core.observability import request_id_from
from app.main import create_app


def _chunked_body(total_bytes: int, chunk_size: int = 100_000) -> Iterator[bytes]:
    remaining = total_bytes
    while remaining > 0:
        size = min(remaining, chunk_size)
        yield b"x" * size
        remaining -= size


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


def test_oversized_content_length_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"Content-Length": "2000000"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": {"code": "payload_too_large"}}
    assert response.headers["X-Request-ID"]


def test_chunked_body_above_limit_is_rejected_before_parsing() -> None:
    app = create_app()

    @app.post("/__test__/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"length": len(body)}

    with TestClient(app) as test_client:
        response = test_client.post("/__test__/echo", content=_chunked_body(1_300_000))

    # Sem Content-Length: o caminho antigo não teria como bloquear pelo header.
    assert "content-length" not in response.request.headers
    assert response.request.headers["transfer-encoding"] == "chunked"
    assert response.status_code == 413
    assert response.json() == {"detail": {"code": "payload_too_large"}}
    assert response.headers["X-Request-ID"]


def test_chunked_body_below_limit_is_parsed_normally() -> None:
    app = create_app()

    @app.post("/__test__/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"length": len(body)}

    with TestClient(app) as test_client:
        response = test_client.post("/__test__/echo", content=_chunked_body(900_000))

    assert response.status_code == 200, response.text
    assert response.json() == {"length": 900_000}


def test_chunked_body_above_limit_is_rejected_on_api_route(client: TestClient) -> None:
    response = client.post("/api/v1/bookings", content=_chunked_body(1_300_000))

    assert response.status_code == 413
    assert response.json() == {"detail": {"code": "payload_too_large"}}
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_method_not_allowed_includes_allow_header(client: TestClient) -> None:
    simulate_path = "/api/v1/bookings/00000000-0000-0000-0000-000000000000/payments/simulate"
    simulate = client.get(simulate_path)
    assert simulate.status_code == 405
    assert simulate.headers["Allow"] == "POST"

    health = client.delete("/api/v1/health/live")
    assert health.status_code == 405
    assert "GET" in health.headers["Allow"]


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


def test_unhandled_exception_returns_500_with_headers() -> None:
    app = create_app()

    @app.get("/__test__/boom")
    def boom() -> None:
        raise RuntimeError("boom-detail")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get(
            "/__test__/boom",
            headers={"X-Request-ID": "boom-request-1"},
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "boom-request-1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert "boom-detail" not in response.text
