"""Ponto de entrada da API JOGA."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.observability import install_observability
from app.modules.email.inline_drain import InlineEmailDrain


def _validation_fields(exc: RequestValidationError) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        fields.append(
            {
                "field": location or "body",
                "code": str(error.get("type", "invalid")),
                "message": str(error.get("msg", "Valor inválido")),
            }
        )
    return fields


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    inline_drain = (
        InlineEmailDrain.from_settings(resolved) if resolved.email_inline_drain_enabled else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.email_inline_drain = inline_drain
        if inline_drain is not None:
            await inline_drain.start()
        try:
            yield
        finally:
            if inline_drain is not None:
                await inline_drain.stop()

    app = FastAPI(
        title="JOGA API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "Dados inválidos",
                    "fields": _validation_fields(exc),
                }
            },
        )

    app.include_router(api_router, prefix="/api/v1")
    app.state.settings = resolved
    install_observability(app, resolved)
    return app


app = create_app()
