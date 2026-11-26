"""Observabilidade HTTP: request ID, headers e log de acesso sem PII.

O log de acesso em stdout continua sendo a trilha completa de borda. O evento
persistido em ``log_events`` (ADR 0078) é um recorte amostrado e sanitizado,
com IP real resolvido na borda e hash. Segurança (401/403/429) é gravada de
forma síncrona na trilha canônica ``security_events``.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.client_version import client_version_error
from app.core.config import Settings, get_settings
from app.core.request_context import (
    bind_request_context,
    normalize_ip,
    reset_request_context,
)
from app.modules.identity.events import HTTP_FORBIDDEN, HTTP_RATE_LIMITED, HTTP_UNAUTHORIZED
from app.modules.identity.phone import hash_ip
from app.modules.observability.service import (
    SLOW_REQUEST_MS,
    LogDispatcher,
    build_entry,
    log_exception,
    reset_dispatcher,
    set_dispatcher,
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"
SKIP_LOG_PATHS = frozenset({"/api/v1/health/live", "/api/v1/health/ready"})

# Aplicados a toda resposta, inclusive erros não tratados. ``no-store`` global,
# inclusive catálogo público (decisão P3-10); header de rota é sobrescrito aqui.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

logger = logging.getLogger("joga.http")

PAYLOAD_TOO_LARGE_BODY = {"detail": {"code": "payload_too_large"}}
PAYLOAD_TOO_LARGE_STATUS = 413

SECURITY_STATUS_EVENTS = {
    401: HTTP_UNAUTHORIZED,
    403: HTTP_FORBIDDEN,
    429: HTTP_RATE_LIMITED,
}


class PayloadTooLarge(HTTPException):
    """Corpo maior que o limite, detectado pela contagem real de bytes."""

    def __init__(self) -> None:
        super().__init__(
            status_code=PAYLOAD_TOO_LARGE_STATUS,
            detail=PAYLOAD_TOO_LARGE_BODY["detail"],
        )


class RequestBodyLimitMiddleware:
    """Rejeita corpos acima do limite contando os bytes do fluxo ASGI.

    ``Content-Length`` não é confiável: um cliente pode omiti-lo e usar
    ``Transfer-Encoding: chunked``. Contamos cada ``http.request`` entregue à
    aplicação e interrompemos a leitura no primeiro byte excedente, antes de a
    rota interpretar o payload. A exceção é ``HTTPException`` porque o FastAPI
    relança esse tipo ao ler o corpo e o handler padrão preserva o 413.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLarge
            return message

        await self.app(scope, limited_receive, send)


def apply_standard_headers(response: Response, request_id: str) -> None:
    """Garante request ID e headers de segurança em qualquer resposta."""
    response.headers[REQUEST_ID_HEADER] = request_id
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value


def request_id_from(value: str | None) -> str:
    """Aceita um ID seguro do cliente ou gera um novo."""
    if value is not None and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid.uuid4().hex


def correlation_id_from(value: str | None, fallback: str) -> str:
    """Aceita correlação segura do cliente; sem ela usa o request ID."""
    if value is not None and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return fallback


def _endpoint_for(request: Request) -> str:
    """Template da rota quando houver; senão o caminho puro, sem query."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return request.url.path


async def _record_security_status(
    dispatcher: LogDispatcher,
    *,
    request: Request,
    status_code: int,
    request_id: str,
    endpoint: str,
    ip: str | None,
    ip_hash: str | None,
    user_id: uuid.UUID | None,
    user_agent: str | None,
) -> None:
    event_type = SECURITY_STATUS_EVENTS.get(status_code)
    if event_type is None:
        return
    await asyncio.to_thread(
        dispatcher.write_security_now,
        event_type,
        user_id=user_id,
        ip=ip,
        ip_hash=ip_hash,
        request_id=request_id,
        endpoint=endpoint,
        user_agent=user_agent,
        result="blocked" if status_code == 429 else "failure",
        details={"method": request.method, "status": status_code},
    )


def install_observability(app: FastAPI, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    # Instalado antes do middleware de observabilidade para que a resposta 413
    # também receba request ID, headers de segurança e log de acesso.
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=resolved.max_request_body_bytes,
    )

    @app.middleware("http")
    async def observability(request: Request, call_next: Any) -> Response:
        request_id = request_id_from(request.headers.get(REQUEST_ID_HEADER))
        correlation_id = correlation_id_from(request.headers.get(CORRELATION_ID_HEADER), request_id)
        ip = normalize_ip(request.client.host if request.client else None)
        ip_hash = hash_ip(ip, resolved.phone_hash_secret.get_secret_value()) if ip else None
        user_agent = request.headers.get("user-agent")
        endpoint = _endpoint_for(request)
        path = request.url.path

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.ip = ip
        request.state.ip_hash = ip_hash

        dispatcher: LogDispatcher | None = getattr(request.app.state, "observability", None)
        context_tokens = bind_request_context(
            request_id=request_id,
            correlation_id=correlation_id,
            ip=ip,
            ip_hash=ip_hash,
            user_agent=user_agent,
            endpoint=endpoint,
            method=request.method,
        )
        dispatcher_token = set_dispatcher(dispatcher) if dispatcher is not None else None

        started = time.perf_counter()
        try:
            try:
                content_length = request.headers.get("content-length")
                too_large = (
                    content_length is not None
                    and content_length.isdigit()
                    and int(content_length) > resolved.max_request_body_bytes
                )
                if too_large:
                    response: Response = JSONResponse(
                        status_code=PAYLOAD_TOO_LARGE_STATUS,
                        content=PAYLOAD_TOO_LARGE_BODY,
                    )
                else:
                    version_error = client_version_error(request, resolved)
                    if version_error is not None:
                        response = version_error
                    else:
                        response = await call_next(request)
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000
                endpoint = _endpoint_for(request) or endpoint
                # Sem traceback cru no stdout: a mensagem pode carregar segredo.
                # O registro sanitizado vai para o log de eventos (ou fallback).
                logger.error(
                    "http_request_unhandled method=%s path=%s duration_ms=%.2f "
                    "request_id=%s error_type=%s",
                    request.method,
                    path,
                    duration_ms,
                    request_id,
                    type(exc).__name__,
                )
                try:
                    log_exception(
                        exc,
                        category="app",
                        module="http",
                        message=(
                            f"unhandled error {request.method} {endpoint}: "
                            f"{type(exc).__name__}: {exc}"
                        ),
                        details={"method": request.method, "endpoint": endpoint},
                    )
                except Exception:  # noqa: BLE001 - observabilidade nunca derruba
                    logger.exception("falha ao enfileirar excecao de request")
                # Não relança: a resposta de erro também precisa de request ID e
                # headers de segurança. O traceback fica no log, nunca no corpo.
                response = JSONResponse(
                    status_code=500,
                    content={"detail": {"code": "internal_error"}},
                )

            duration_ms = (time.perf_counter() - started) * 1000
            apply_standard_headers(response, request_id)
            if path not in SKIP_LOG_PATHS:
                logger.info(
                    "http_request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
                    request.method,
                    path,
                    response.status_code,
                    duration_ms,
                    request_id,
                )
                if dispatcher is not None:
                    await _record_http_event(
                        dispatcher,
                        request=request,
                        response=response,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        endpoint=endpoint,
                        ip=ip,
                        ip_hash=ip_hash,
                        user_agent=user_agent,
                        duration_ms=duration_ms,
                    )
            return response
        finally:
            if dispatcher_token is not None:
                reset_dispatcher(dispatcher_token)
            reset_request_context(context_tokens)

    async def _record_http_event(
        dispatcher: LogDispatcher,
        *,
        request: Request,
        response: Response,
        request_id: str,
        correlation_id: str,
        endpoint: str,
        ip: str | None,
        ip_hash: str | None,
        user_agent: str | None,
        duration_ms: float,
    ) -> None:
        endpoint = _endpoint_for(request) or endpoint
        status_code = response.status_code
        rounded_ms = int(round(duration_ms))
        slow = rounded_ms > SLOW_REQUEST_MS
        sample_rate = getattr(
            dispatcher.settings,
            "log_http_success_sample_rate",
            resolved.log_http_success_sample_rate,
        )
        if 200 <= status_code < 300 and not slow:
            if random.random() > sample_rate:
                return
        level = "error" if status_code >= 500 else "warn"
        if status_code < 400 and not slow:
            level = "info"
        user_id = getattr(request.state, "user_id", None)
        try:
            dispatcher.submit(
                build_entry(
                    level=level,
                    category="http",
                    module="http",
                    message=f"{request.method} {endpoint} {status_code}",
                    request_id=request_id,
                    correlation_id=correlation_id,
                    user_id=user_id,
                    ip=ip,
                    ip_hash=ip_hash,
                    user_agent=user_agent,
                    endpoint=endpoint,
                    status=status_code,
                    duration_ms=rounded_ms,
                    details={"method": request.method, "slow": slow},
                    use_request_context=False,
                )
            )
            if status_code in SECURITY_STATUS_EVENTS:
                await _record_security_status(
                    dispatcher,
                    request=request,
                    status_code=status_code,
                    request_id=request_id,
                    endpoint=endpoint,
                    ip=ip,
                    ip_hash=ip_hash,
                    user_id=user_id,
                    user_agent=user_agent,
                )
        except Exception:  # noqa: BLE001 - a resposta nunca falha por observabilidade
            logger.exception("falha ao registrar evento HTTP")
