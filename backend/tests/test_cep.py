"""Testes do resolvedor de CEP (BrasilAPI, sem rede)."""

import urllib.error

import pytest

from app.modules.profile.cep import (
    BrasilApiCepResolver,
    CepNotFound,
    CepProviderUnavailable,
    InvalidCep,
    _urlopen_json,
    normalize_cep,
)


def test_normalize_cep_accepts_formatting() -> None:
    assert normalize_cep("01001-000") == "01001000"
    assert normalize_cep("01001000") == "01001000"


@pytest.mark.parametrize("value", ["123", "00000000", "abcdefgh", ""])
def test_normalize_cep_rejects_invalid(value: str) -> None:
    with pytest.raises(InvalidCep):
        normalize_cep(value)


def payload() -> dict[str, object]:
    return {
        "cep": "01001000",
        "city": "São Paulo",
        "state": "SP",
        "location": {
            "type": "Point",
            "coordinates": {"latitude": "-23.5503898", "longitude": "-46.633081"},
        },
    }


def test_resolver_parses_location_and_caches() -> None:
    calls: list[str] = []

    def fetch(url: str, timeout: float) -> dict[str, object]:
        calls.append(url)
        return payload()

    resolver = BrasilApiCepResolver("https://example.test/cep", fetch_json=fetch)

    first = resolver.resolve("01001-000")
    second = resolver.resolve("01001000")

    assert first == second
    assert first.city == "São Paulo"
    assert first.state == "SP"
    assert first.lat == pytest.approx(-23.5503898)
    assert len(calls) == 1


def test_urlopen_sends_identifiable_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regressão: o BrasilAPI responde 403 ao User-Agent padrão do urllib."""
    captured: dict[str, str] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        captured.update(request.headers)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert _urlopen_json("https://example.test/cep", 1.0) == {}
    assert captured["User-agent"].startswith("JOGA/")


def test_resolver_maps_404_to_not_found() -> None:
    def fetch(url: str, timeout: float) -> dict[str, object]:
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    resolver = BrasilApiCepResolver("https://example.test/cep", fetch_json=fetch)

    with pytest.raises(CepNotFound):
        resolver.resolve("01001000")


def test_resolver_maps_missing_coordinates_to_unavailable() -> None:
    def fetch(url: str, timeout: float) -> dict[str, object]:
        return {"city": "São Paulo", "state": "SP", "location": None}

    resolver = BrasilApiCepResolver("https://example.test/cep", fetch_json=fetch)

    with pytest.raises(CepProviderUnavailable):
        resolver.resolve("01001000")


def test_resolver_maps_timeout_to_unavailable() -> None:
    def fetch(url: str, timeout: float) -> dict[str, object]:
        raise TimeoutError("timeout")

    resolver = BrasilApiCepResolver("https://example.test/cep", fetch_json=fetch)

    with pytest.raises(CepProviderUnavailable):
        resolver.resolve("01001000")
