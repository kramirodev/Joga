"""Resolução de CEP via BrasilAPI CEP v2 (cidade/UF + coordenadas)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

CEP_PATTERN = re.compile(r"^\d{8}$")


class CepError(Exception):
    """Erro base de resolução de CEP."""


class InvalidCep(CepError):
    """CEP fora do formato de oito dígitos."""


class CepNotFound(CepError):
    """CEP inexistente na base consultada."""


class CepProviderUnavailable(CepError):
    """Provedor de CEP indisponível ou sem coordenadas."""


class CepTimeout(CepProviderUnavailable):
    """Provedor de CEP excedeu o tempo limite."""


@dataclass(frozen=True)
class CepLocation:
    cep: str
    city: str
    state: str
    lat: float
    lng: float


@dataclass(frozen=True)
class PostalCodeLocation:
    cep: str
    street: str | None
    neighborhood: str | None
    city: str
    state: str
    country: str
    lat: float | None
    lng: float | None
    precision: str
    source: str


class CepResolver(Protocol):
    def resolve(self, cep: str) -> CepLocation: ...


def normalize_cep(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not CEP_PATTERN.fullmatch(digits) or digits == "00000000":
        raise InvalidCep("CEP deve ter oito dígitos")
    return digits


FetchJson = Callable[[str, float], dict[str, object]]


class BrasilApiCepResolver:
    """Consulta o BrasilAPI; testes injetam `fetch_json` sem rede."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 5.0,
        fetch_json: FetchJson | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._fetch_json = fetch_json or _urlopen_json
        self._cache: dict[str, CepLocation] = {}
        self._postal_cache: dict[str, PostalCodeLocation] = {}

    def resolve(self, cep: str) -> CepLocation:
        normalized = normalize_cep(cep)
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        postal = self.resolve_postal_code(normalized)
        if postal.lat is None or postal.lng is None:
            raise CepProviderUnavailable("CEP sem coordenadas disponíveis")
        location = CepLocation(
            cep=postal.cep,
            city=postal.city,
            state=postal.state,
            lat=postal.lat,
            lng=postal.lng,
        )
        self._cache[normalized] = location
        return location

    def resolve_postal_code(self, cep: str) -> PostalCodeLocation:
        normalized = normalize_cep(cep)
        cached = self._postal_cache.get(normalized)
        if cached is not None:
            return cached
        url = f"{self._base_url}/{normalized}"
        try:
            payload = self._fetch_json(url, self._timeout)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise CepNotFound("CEP não encontrado") from error
            raise CepProviderUnavailable("provedor de CEP indisponível") from error
        except TimeoutError as error:
            raise CepTimeout("provedor de CEP excedeu o tempo limite") from error
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            if isinstance(getattr(error, "reason", None), TimeoutError):
                raise CepTimeout("provedor de CEP excedeu o tempo limite") from error
            raise CepProviderUnavailable("provedor de CEP indisponível") from error

        city = payload.get("city")
        state = payload.get("state")
        if not isinstance(city, str) or not isinstance(state, str):
            raise CepProviderUnavailable("resposta de CEP inválida")

        street = payload.get("street")
        neighborhood = payload.get("neighborhood")
        location = payload.get("location")
        coordinates = location.get("coordinates") if isinstance(location, dict) else None
        lat: float | None = None
        lng: float | None = None
        if isinstance(coordinates, dict):
            try:
                lat = float(coordinates["latitude"])
                lng = float(coordinates["longitude"])
            except (KeyError, TypeError, ValueError):
                lat = None
                lng = None
            if lat is not None and lng is not None:
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    lat = None
                    lng = None

        if lat is not None and lng is not None:
            precision = "street" if isinstance(street, str) and street else "approximate"
        else:
            precision = "unresolved"

        result = PostalCodeLocation(
            cep=normalized,
            street=street if isinstance(street, str) and street else None,
            neighborhood=(neighborhood if isinstance(neighborhood, str) and neighborhood else None),
            city=city,
            state=state.upper()[:2],
            country="BR",
            lat=lat,
            lng=lng,
            precision=precision,
            source="brasilapi",
        )
        self._postal_cache[normalized] = result
        return result


REQUEST_HEADERS = {
    # O BrasilAPI atrás do Cloudflare responde 403 ao User-Agent padrão do urllib.
    "User-Agent": "JOGA/0.1 (local; contato: dev@joga.invalid)",
    "Accept": "application/json",
}


def _urlopen_json(url: str, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise CepProviderUnavailable("resposta de CEP inválida")
    return {str(key): value for key, value in parsed.items()}
