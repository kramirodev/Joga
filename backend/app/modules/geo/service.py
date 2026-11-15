"""Resolução de CEP para estabelecimentos, com cache persistente (Fase 1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.geo.models import PostalCodeCache
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.profile.cep import (
    CepNotFound,
    CepProviderUnavailable,
    CepTimeout,
    InvalidCep,
    PostalCodeLocation,
    normalize_cep,
)


class PostalCodeResolver(Protocol):
    def resolve_postal_code(self, cep: str) -> PostalCodeLocation: ...


@dataclass(frozen=True)
class PostalCodeResult:
    location: PostalCodeLocation
    resolved_at: datetime


class PostalCodeService:
    """Resolve CEP e mantém cache por CEP+número+versão do provedor."""

    def __init__(
        self,
        session: Session,
        resolver: PostalCodeResolver,
        *,
        ttl_days: int = 30,
        provider_version: str = "brasilapi_v1",
    ) -> None:
        self.session = session
        self.resolver = resolver
        self.ttl = timedelta(days=ttl_days)
        self.provider_version = provider_version

    def resolve(self, postal_code: str, number: str | None = None) -> PostalCodeResult:
        normalized = normalize_cep(postal_code)
        normalized_number = _normalize_number(number)
        cache_key = f"{self.provider_version}:{normalized}:{normalized_number or ''}"
        now = ensure_utc(utcnow())

        cached = self.session.get(PostalCodeCache, cache_key)
        if cached is not None:
            if ensure_utc(cached.expires_at) > now:
                return PostalCodeResult(
                    location=_location_from_payload(cached.payload),
                    resolved_at=ensure_utc(cached.resolved_at),
                )
            self.session.delete(cached)
            self.session.flush()

        location = self.resolver.resolve_postal_code(normalized)
        resolved_at = ensure_utc(utcnow())
        row = PostalCodeCache(
            cache_key=cache_key,
            postal_code=normalized,
            number=normalized_number,
            provider=self.provider_version,
            payload=_payload_from_location(location),
            resolved_at=resolved_at,
            expires_at=resolved_at + self.ttl,
            created_at=resolved_at,
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            concurrent = self.session.get(PostalCodeCache, cache_key)
            if concurrent is not None:
                return PostalCodeResult(
                    location=_location_from_payload(concurrent.payload),
                    resolved_at=ensure_utc(concurrent.resolved_at),
                )
            raise
        return PostalCodeResult(location=location, resolved_at=resolved_at)


def _normalize_number(number: str | None) -> str | None:
    if number is None:
        return None
    cleaned = number.strip()
    return cleaned or None


def _payload_from_location(location: PostalCodeLocation) -> dict[str, object]:
    return {
        "postal_code": location.cep,
        "street": location.street,
        "neighborhood": location.neighborhood,
        "city": location.city,
        "state": location.state,
        "country": location.country,
        "latitude": location.lat,
        "longitude": location.lng,
        "precision": location.precision,
        "source": location.source,
    }


def _location_from_payload(payload: dict[str, object]) -> PostalCodeLocation:
    street_raw = payload.get("street")
    neighborhood_raw = payload.get("neighborhood")
    lat_raw = payload.get("latitude")
    lng_raw = payload.get("longitude")
    return PostalCodeLocation(
        cep=str(payload["postal_code"]),
        street=street_raw if isinstance(street_raw, str) else None,
        neighborhood=neighborhood_raw if isinstance(neighborhood_raw, str) else None,
        city=str(payload["city"]),
        state=str(payload["state"]),
        country=str(payload.get("country", "BR")),
        lat=float(lat_raw) if isinstance(lat_raw, int | float) else None,
        lng=float(lng_raw) if isinstance(lng_raw, int | float) else None,
        precision=str(payload["precision"]),
        source=str(payload["source"]),
    )


__all__ = [
    "CepNotFound",
    "CepProviderUnavailable",
    "CepTimeout",
    "InvalidCep",
    "PostalCodeResolver",
    "PostalCodeResult",
    "PostalCodeService",
]
