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


@dataclass(frozen=True)
class CepLocation:
    cep: str
    city: str
    state: str
    lat: float
    lng: float


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

    def resolve(self, cep: str) -> CepLocation:
        normalized = normalize_cep(cep)
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        url = f"{self._base_url}/{normalized}"
        try:
            payload = self._fetch_json(url, self._timeout)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise CepNotFound("CEP não encontrado") from error
            raise CepProviderUnavailable("provedor de CEP indisponível") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise CepProviderUnavailable("provedor de CEP indisponível") from error

        city = payload.get("city")
        state = payload.get("state")
        location = payload.get("location")
        coordinates = location.get("coordinates") if isinstance(location, dict) else None
        if (
            not isinstance(city, str)
            or not isinstance(state, str)
            or not isinstance(coordinates, dict)
        ):
            raise CepProviderUnavailable("CEP sem coordenadas disponíveis")

        try:
            lat = float(coordinates["latitude"])
            lng = float(coordinates["longitude"])
        except (KeyError, TypeError, ValueError) as error:
            raise CepProviderUnavailable("CEP sem coordenadas disponíveis") from error

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise CepProviderUnavailable("coordenadas de CEP inválidas")

        location = CepLocation(
            cep=normalized,
            city=city,
            state=state.upper()[:2],
            lat=lat,
            lng=lng,
        )
        self._cache[normalized] = location
        return location


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
