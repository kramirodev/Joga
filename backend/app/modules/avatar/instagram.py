"""Importação temporária da foto pública do próprio perfil do Instagram.

Este caminho existe apenas para o beta fechado (Onda 1.7), autorizado pelo dono
como medida temporária. Ele **não** é integração oficial: a extração depende do
HTML público, não guarda a página, não guarda a URL assinada da CDN e pode parar
de funcionar sem aviso. A API oficial da Meta substitui este módulo.

Regras de segurança aplicadas aqui:
- apenas ``https`` e host ``instagram.com``/``www.instagram.com`` na página;
- no máximo um redirect, sempre revalidado contra a allowlist;
- resolução DNS precisa devolver somente IP global (anti-SSRF/rebinding);
- imagem apenas ``https`` em ``*.cdninstagram.com``/``*.fbcdn.net``;
- sem proxy de ambiente (``trust_env=False``), cookies ou login;
- limites rígidos de bytes na página (512 KB) e na imagem (5 MB).
"""

from __future__ import annotations

import html as html_module
import ipaddress
import json
import re
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx

from app.modules.avatar.photos import (
    AVATAR_SIDE,
    InvalidAvatarImage,
    process_avatar,
)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")
PAGE_HOSTS = frozenset({"instagram.com", "www.instagram.com"})
IMAGE_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
PAGE_MAX_BYTES = 512 * 1024
IMAGE_MAX_BYTES = 5_000_000
MAX_REDIRECTS = 1

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_PRIVATE_PATTERN = re.compile(r'"is_private"\s*:\s*true', re.IGNORECASE)
_OG_IMAGE_PROPERTY = re.compile(r"""property\s*=\s*["']og:image["']""", re.IGNORECASE)
_META_CONTENT = re.compile(r"""content\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_PROFILE_PIC_PATTERN = re.compile(
    r'"profile_pic_url_hd"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.IGNORECASE,
)
_MISSING_MARKERS = (
    "sorry, this page isn't available",
    "the link you followed may be broken",
    "page not found",
)
_LOGIN_MARKERS = (
    "/accounts/login/",
    "loginandsignuppage",
    '"login_required":true',
    "please wait a few minutes before you try again",
)

PAGE_HEADERS: Mapping[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
IMAGE_HEADERS: Mapping[str, str] = {
    "User-Agent": PAGE_HEADERS["User-Agent"],
    "Accept": "image/jpeg,image/png,image/webp",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class InstagramImportError(Exception):
    """Erro base da importação temporária."""

    code = "instagram_unavailable"


class InvalidInstagramUrl(InstagramImportError):
    """URL fora do contrato do próprio perfil público."""

    code = "invalid_instagram_url"


class InstagramProfileNotFound(InstagramImportError):
    """Perfil público inexistente."""

    code = "instagram_profile_not_found"


class InstagramProfilePrivate(InstagramImportError):
    """Perfil privado; a foto não é pública."""

    code = "instagram_profile_private"


class InstagramImageTooLarge(InstagramImportError):
    """Imagem acima do limite de 5 MB."""

    code = "image_too_large"


class InvalidInstagramImage(InstagramImportError):
    """Imagem baixada não é JPEG/PNG/WebP válida."""

    code = "invalid_instagram_image"


class InstagramUnavailable(InstagramImportError):
    """Instagram indisponível, login wall, timeout ou resposta inesperada."""

    code = "instagram_unavailable"


@dataclass(frozen=True)
class ParsedProfile:
    username: str
    page_url: str


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""
    truncated: bool = False


@dataclass(frozen=True)
class InstagramPhoto:
    """Foto já validada e reencodada; ainda sem persistência."""

    username: str
    page_url: str
    data: bytes
    content_type: str
    width: int
    height: int


class HttpTransport(Protocol):
    """Uma requisição GET sem seguir redirects automaticamente."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_bytes: int,
    ) -> HttpResponse: ...


HostResolver = Callable[[str], list[str]]


class HttpxTransport:
    """Transporte HTTP mínimo: sem proxy de ambiente, cookies ou redirects."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_bytes: int,
    ) -> HttpResponse:
        try:
            with httpx.Client(
                follow_redirects=False,
                trust_env=False,
                timeout=timeout_seconds,
            ) as client:
                with client.stream("GET", url, headers=dict(headers)) as response:
                    normalized_headers = {
                        key.lower(): value for key, value in response.headers.items()
                    }
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            return HttpResponse(
                                status_code=response.status_code,
                                headers=normalized_headers,
                                truncated=True,
                            )
                        chunks.append(chunk)
                    return HttpResponse(
                        status_code=response.status_code,
                        headers=normalized_headers,
                        content=b"".join(chunks),
                    )
        except httpx.HTTPError as exc:
            raise InstagramUnavailable("falha ao consultar o Instagram") from exc


def _resolve_public_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise InstagramUnavailable("não foi possível resolver o host") from exc
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses:
        raise InstagramUnavailable("host sem endereço")
    return addresses


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _is_page_host(host: str) -> bool:
    return host in PAGE_HOSTS


def _is_image_host(host: str) -> bool:
    return any(host.endswith(suffix) for suffix in IMAGE_HOST_SUFFIXES)


def parse_profile_url(raw: str) -> ParsedProfile:
    """Aceita somente o perfil público no formato e host canônicos."""

    if not isinstance(raw, str):
        raise InvalidInstagramUrl("url deve ser texto")
    candidate = raw.strip()
    if not candidate or len(candidate) > 300:
        raise InvalidInstagramUrl("url inválida")
    parts = _split_https_url(candidate, error=InvalidInstagramUrl)
    if parts.query or parts.fragment:
        raise InvalidInstagramUrl("url não pode ter query ou fragmento")
    if not _is_page_host((parts.hostname or "").lower().rstrip(".")):
        raise InvalidInstagramUrl("host não permitido")
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) != 1:
        raise InvalidInstagramUrl("a url deve apontar para um único perfil")
    username = segments[0]
    if not USERNAME_PATTERN.fullmatch(username):
        raise InvalidInstagramUrl("nome de usuário inválido")
    return ParsedProfile(
        username=username,
        page_url=f"https://www.instagram.com/{username}/",
    )


def _split_https_url(raw: str, *, error: type[InstagramImportError]) -> SplitResult:
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise error("url inválida") from exc
    if parts.scheme.lower() != "https":
        raise error("somente https é aceito")
    if parts.username is not None or parts.password is not None:
        raise error("url não pode conter credenciais")
    try:
        port = parts.port
    except ValueError as exc:
        raise error("porta inválida") from exc
    if port is not None:
        raise error("porta explícita não é aceita")
    if not parts.hostname:
        raise error("host ausente")
    return parts


class InstagramImporter:
    """Busca, valida e normaliza a foto pública do perfil informado."""

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        resolver: HostResolver | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._resolver = resolver or _resolve_public_ips
        self._timeout_seconds = timeout_seconds

    def fetch(self, raw_url: str) -> InstagramPhoto:
        parsed = parse_profile_url(raw_url)
        page = self._request(
            parsed.page_url,
            headers=PAGE_HEADERS,
            max_bytes=PAGE_MAX_BYTES,
            allowed_host=_is_page_host,
        )
        _raise_for_page_status(page)
        if len(page.content) > PAGE_MAX_BYTES:
            raise InstagramUnavailable("página acima do limite")
        text = page.content.decode("utf-8", errors="replace")

        if _is_missing_profile(text):
            raise InstagramProfileNotFound("perfil não encontrado")
        if _PRIVATE_PATTERN.search(text):
            raise InstagramProfilePrivate("perfil privado")

        image_url = _extract_image_url(text)
        if image_url is None:
            if _is_login_wall(text):
                raise InstagramUnavailable("login wall do Instagram")
            raise InstagramUnavailable("página sem foto pública")

        try:
            image = self._request(
                image_url,
                headers=IMAGE_HEADERS,
                max_bytes=IMAGE_MAX_BYTES,
                allowed_host=_is_image_host,
            )
        except _ResponseTooLarge as exc:
            raise InstagramImageTooLarge("imagem acima do limite") from exc
        if image.status_code != 200:
            raise InstagramUnavailable("imagem indisponível")
        if len(image.content) > IMAGE_MAX_BYTES:
            raise InstagramImageTooLarge("imagem acima do limite")

        try:
            processed = process_avatar(image.content, max_bytes=IMAGE_MAX_BYTES)
        except InvalidAvatarImage as exc:
            raise InvalidInstagramImage("imagem inválida") from exc

        return InstagramPhoto(
            username=parsed.username,
            page_url=parsed.page_url,
            data=processed.data,
            content_type=processed.content_type,
            width=processed.width,
            height=processed.height,
        )

    def _request(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        max_bytes: int,
        allowed_host: Callable[[str], bool],
    ) -> HttpResponse:
        current = url
        redirects = 0
        while True:
            parts = _split_https_url(current, error=InstagramUnavailable)
            host = (parts.hostname or "").lower().rstrip(".")
            if not allowed_host(host):
                raise InstagramUnavailable("host final fora da allowlist")
            self._assert_public_host(host)

            response = self._transport.get(
                current,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
                max_bytes=max_bytes,
            )
            if response.status_code in _REDIRECT_STATUSES:
                if redirects >= MAX_REDIRECTS:
                    raise InstagramUnavailable("redirects demais")
                location = _header(response.headers, "location")
                if not location:
                    raise InstagramUnavailable("redirect sem destino")
                current = urljoin(current, location)
                redirects += 1
                continue
            if response.truncated:
                raise _ResponseTooLarge
            return response

    def _assert_public_host(self, host: str) -> None:
        try:
            addresses = self._resolver(host)
        except InstagramImportError:
            raise
        except OSError as exc:
            raise InstagramUnavailable("falha de resolução DNS") from exc
        if not addresses:
            raise InstagramUnavailable("host sem endereço")
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw)
            except ValueError as exc:
                raise InstagramUnavailable("endereço DNS inválido") from exc
            if not address.is_global:
                raise InstagramUnavailable("host resolve para IP não público")


class _ResponseTooLarge(Exception):
    """Resposta excedeu o limite de bytes solicitado."""


def _raise_for_page_status(response: HttpResponse) -> None:
    if 200 <= response.status_code < 300:
        return
    if response.status_code == 404:
        raise InstagramProfileNotFound("perfil não encontrado")
    if response.status_code == 429:
        raise InstagramUnavailable("Instagram limitou a requisição")
    raise InstagramUnavailable("página indisponível")


def _is_missing_profile(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _MISSING_MARKERS)


def _is_login_wall(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _LOGIN_MARKERS)


def _decode_js_string(value: str) -> str:
    decoded = html_module.unescape(value).replace("\\/", "/")
    try:
        parsed = json.loads(f'"{decoded}"')
    except (json.JSONDecodeError, ValueError):
        return decoded
    return parsed if isinstance(parsed, str) else decoded


def _extract_image_url(text: str) -> str | None:
    for tag in re.findall(r"<meta\b[^>]*>", text, flags=re.IGNORECASE):
        if not _OG_IMAGE_PROPERTY.search(tag):
            continue
        content = _META_CONTENT.search(tag)
        if content is not None:
            candidate = html_module.unescape(content.group(1)).strip()
            if candidate.startswith("https://"):
                return candidate

    fallback = _PROFILE_PIC_PATTERN.search(text)
    if fallback is not None:
        candidate = _decode_js_string(fallback.group(1)).strip()
        if candidate.startswith("https://"):
            return candidate
    return None


__all__ = [
    "AVATAR_SIDE",
    "HttpTransport",
    "InstagramImageTooLarge",
    "InstagramImportError",
    "InstagramImporter",
    "InstagramPhoto",
    "InstagramProfileNotFound",
    "InstagramProfilePrivate",
    "InstagramUnavailable",
    "InvalidInstagramImage",
    "InvalidInstagramUrl",
    "parse_profile_url",
]
