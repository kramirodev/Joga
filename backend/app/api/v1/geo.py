"""Consulta de CEP para cadastro de estabelecimento (Fase 1)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.geo.service import (
    CepNotFound,
    CepProviderUnavailable,
    CepTimeout,
    InvalidCep,
    PostalCodeResolver,
    PostalCodeService,
)
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.profile.cep import BrasilApiCepResolver
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.ratelimit.service import enforce as enforce_rate_limit

router = APIRouter(prefix="/geo", tags=["geo"])


class PostalCodeResponse(BaseModel):
    postal_code: str
    street: str | None
    neighborhood: str | None
    city: str
    state: str
    country: str
    latitude: float | None
    longitude: float | None
    precision: str
    source: str
    resolved_at: datetime


def _error(
    code: str,
    status_code: int,
    *,
    retry_after: int | None = None,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return HTTPException(status_code=status_code, detail={"code": code}, headers=headers)


@lru_cache(maxsize=4)
def _build_postal_code_resolver(
    base_url: str,
    timeout_seconds: float,
) -> PostalCodeResolver:
    return BrasilApiCepResolver(base_url, timeout_seconds=timeout_seconds)


def get_postal_code_resolver(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PostalCodeResolver:
    return _build_postal_code_resolver(
        settings.cep_api_base_url,
        settings.geo_timeout_seconds,
    )


def get_postal_code_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    resolver: Annotated[PostalCodeResolver, Depends(get_postal_code_resolver)],
) -> PostalCodeService:
    return PostalCodeService(
        session,
        resolver,
        ttl_days=settings.geo_cache_ttl_days,
        provider_version=settings.geo_provider_version,
    )


@router.get("/postal-codes/{postal_code}", response_model=PostalCodeResponse)
def resolve_postal_code(
    postal_code: str,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[PostalCodeService, Depends(get_postal_code_service)],
    number: Annotated[str | None, Query(max_length=20)] = None,
) -> PostalCodeResponse:
    try:
        enforce_rate_limit(
            session,
            scope="geo_postal_code",
            key=str(current.user_id),
            limit=settings.geo_rate_limit_per_minute,
        )
    except RateLimitExceeded as exc:
        session.rollback()
        raise _error(
            "rate_limited",
            status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=exc.retry_after_seconds,
        ) from None
    # Persistir o contador mesmo se o provedor falhar.
    session.commit()

    try:
        result = service.resolve(postal_code, number)
    except InvalidCep:
        raise _error(
            "invalid_postal_code",
            status.HTTP_400_BAD_REQUEST,
        ) from None
    except CepNotFound:
        raise _error(
            "postal_code_not_found",
            status.HTTP_404_NOT_FOUND,
        ) from None
    except CepTimeout:
        session.rollback()
        raise _error(
            "geocoding_timeout",
            status.HTTP_504_GATEWAY_TIMEOUT,
        ) from None
    except CepProviderUnavailable:
        session.rollback()
        raise _error(
            "geocoding_provider_error",
            status.HTTP_502_BAD_GATEWAY,
        ) from None

    session.commit()
    location = result.location
    return PostalCodeResponse(
        postal_code=location.cep,
        street=location.street,
        neighborhood=location.neighborhood,
        city=location.city,
        state=location.state,
        country=location.country,
        latitude=location.lat,
        longitude=location.lng,
        precision=location.precision,
        source=location.source,
        resolved_at=result.resolved_at,
    )


__all__ = ["router"]
