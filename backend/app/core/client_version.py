"""Política de versão mínima do app mobile (ADR 0051).

O gate não é uma fronteira de segurança: headers podem ser falsificados. Ele
serve para impedir que binários antigos conhecidos continuem consumindo a API
depois de uma mudança de contrato. Autorização, rate limit e integridade
continuam no servidor.

Regras:
- clientes ``X-Client: web`` passam (o painel é atualizado junto com o backend);
- clientes mobile precisam de ``X-App-Version`` >= mínimo;
- sem ``X-Client``, um User-Agent mobile (OkHttp/CFNetwork/Expo) é tratado como
  app antigo e bloqueado;
- navegador, curl, health e o próprio app-config passam.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.versioning import Version, parse_version

CLIENT_HEADER = "X-Client"
VERSION_HEADER = "X-App-Version"
PLATFORM_HEADER = "X-Platform"
BUILD_HEADER = "X-Build-Number"

EXEMPT_PATHS = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/app-config",
    }
)
MOBILE_CLIENTS = frozenset({"mobile", "android", "ios"})
MOBILE_USER_AGENT_MARKERS = (
    "okhttp",
    "cfnetwork",
    "expo/",
    "react-native",
    "joga-mobile",
)


@dataclass(frozen=True)
class ClientIdentity:
    """Cliente identificado a partir dos headers, sem confiar no payload."""

    kind: str
    version: Version | None
    raw_version: str | None
    platform: str | None


def identify_client(request: Request) -> ClientIdentity:
    """Classifica a origem como ``mobile``, ``web`` ou ``unknown``."""
    return identify_headers(request.headers)


def identify_headers(headers: Mapping[str, str]) -> ClientIdentity:
    """Variante para HTTP e WebSocket, sem depender de ``Request``."""
    raw_client = headers.get(CLIENT_HEADER)
    client = raw_client.strip().lower() if raw_client else ""
    raw_version = headers.get(VERSION_HEADER)
    platform = headers.get(PLATFORM_HEADER)
    version = parse_version(raw_version)

    if client == "web":
        return ClientIdentity("web", version, raw_version, platform)
    if client in MOBILE_CLIENTS:
        return ClientIdentity("mobile", version, raw_version, platform)
    if client:
        return ClientIdentity("unknown", version, raw_version, platform)

    user_agent = headers.get("user-agent", "").lower()
    if any(marker in user_agent for marker in MOBILE_USER_AGENT_MARKERS):
        return ClientIdentity("mobile", version, raw_version, platform)
    return ClientIdentity("web", version, raw_version, platform)


def blocked_client_code(
    headers: Mapping[str, str],
    path: str,
    settings: Settings,
) -> str | None:
    """Código do bloqueio, se houver; usado por HTTP e WebSocket."""
    if not settings.app_version_gate_enabled:
        return None
    if not path.startswith("/api/v1/") or path in EXEMPT_PATHS:
        return None

    identity = identify_headers(headers)
    if identity.kind == "web":
        return None
    if identity.kind == "unknown":
        return "unsupported_client"
    minimum = parse_version(settings.min_app_version) or (0, 0, 0)
    if identity.version is None or identity.version < minimum:
        return "app_update_required"
    return None


def update_required_for(request: Request, settings: Settings) -> bool:
    """Indica se o chamador mobile está abaixo da versão mínima."""
    if not settings.app_version_gate_enabled:
        return False
    identity = identify_client(request)
    if identity.kind != "mobile":
        return False
    minimum = parse_version(settings.min_app_version) or (0, 0, 0)
    return identity.version is None or identity.version < minimum


def client_version_error(request: Request, settings: Settings) -> JSONResponse | None:
    """Resposta 426 quando o gate está ativo e o cliente mobile está velho."""
    code = blocked_client_code(request.headers, request.url.path, settings)
    if code is None:
        return None
    return _version_error(settings, code)


def _version_error(settings: Settings, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_426_UPGRADE_REQUIRED,
        content={
            "detail": {
                "code": code,
                "min_supported_version": settings.min_app_version,
                "latest_version": settings.latest_app_version,
                "update_url": settings.app_update_url,
            }
        },
    )


__all__ = [
    "BUILD_HEADER",
    "CLIENT_HEADER",
    "ClientIdentity",
    "EXEMPT_PATHS",
    "PLATFORM_HEADER",
    "VERSION_HEADER",
    "blocked_client_code",
    "client_version_error",
    "identify_client",
    "identify_headers",
    "update_required_for",
]
