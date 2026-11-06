"""Observabilidade HTTP: request ID, headers e log de acesso sem PII."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
REQUEST_ID_HEADER = "X-Request-ID"
SKIP_LOG_PATHS = frozenset({"/api/v1/health/live", "/api/v1/health/ready"})

logger = logging.getLogger("joga.http")


def request_id_from(value: str | None) -> str:
    """Aceita um ID seguro do cliente ou gera um novo."""
    if value is not None and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid.uuid4().hex


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def observability(request: Request, call_next: Any) -> Response:
        request_id = request_id_from(request.headers.get(REQUEST_ID_HEADER))
        started = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "http_request method=%s path=%s status=500 duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path not in SKIP_LOG_PATHS:
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
            )
        return response
