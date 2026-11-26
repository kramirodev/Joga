"""Geocodificação de endereço a partir do CEP, compartilhada entre routers.

As coordenadas nunca são derivadas do cliente: quando o CEP é informado e falta
latitude ou longitude, o provedor de CEP resolve o ponto. Campos já informados
pelo operador têm precedência.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.geo.service import PostalCodeService


@dataclass(frozen=True)
class GeocodeOverrides:
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    address_line: str | None = None
    geocoding_source: str | None = None
    geocoding_precision: str | None = None


def geocode_if_needed(
    *,
    postal_service: PostalCodeService,
    postal_code: str | None,
    latitude: float | None,
    longitude: float | None,
    city: str | None,
    state: str | None,
    address_line: str | None,
) -> GeocodeOverrides:
    if not postal_code:
        return GeocodeOverrides()
    if latitude is not None and longitude is not None:
        return GeocodeOverrides(postal_code=postal_code)
    result = postal_service.resolve(postal_code)
    location = result.location
    return GeocodeOverrides(
        postal_code=location.cep,
        latitude=location.lat if latitude is None else latitude,
        longitude=location.lng if longitude is None else longitude,
        city=location.city if city is None else city,
        state=location.state if state is None else state,
        address_line=location.street if address_line is None and location.street else address_line,
        geocoding_source=location.source,
        geocoding_precision=location.precision,
    )


__all__ = ["GeocodeOverrides", "geocode_if_needed"]
