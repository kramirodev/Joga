"""Contexto da requisição corrente para logs, segurança e auditoria.

O middleware preenche estes valores antes de chamar a aplicação e os restaura
ao final. Como o ``contextvars`` propaga para a tarefa interna criada pelo
middleware, rotas e serviços leem o contexto sem receber ``Request`` em toda
assinatura. O ``user_id`` é preenchido pela dependência de autenticação.
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from fastapi import Request

from app.core.config import Settings
from app.modules.identity.phone import hash_ip

request_id_var: ContextVar[str | None] = ContextVar("joga_request_id", default=None)
correlation_id_var: ContextVar[str | None] = ContextVar("joga_correlation_id", default=None)
user_id_var: ContextVar[uuid.UUID | None] = ContextVar("joga_user_id", default=None)
ip_var: ContextVar[str | None] = ContextVar("joga_ip", default=None)
ip_hash_var: ContextVar[str | None] = ContextVar("joga_ip_hash", default=None)
user_agent_var: ContextVar[str | None] = ContextVar("joga_user_agent", default=None)
endpoint_var: ContextVar[str | None] = ContextVar("joga_endpoint", default=None)
method_var: ContextVar[str | None] = ContextVar("joga_method", default=None)


def bind_request_context(
    *,
    request_id: str | None,
    correlation_id: str | None,
    ip: str | None,
    ip_hash: str | None,
    user_agent: str | None,
    endpoint: str | None,
    method: str | None,
) -> list[Token[str | None]]:
    """Associa o contexto da requisição à tarefa corrente."""
    return [
        request_id_var.set(request_id),
        correlation_id_var.set(correlation_id),
        ip_var.set(ip),
        ip_hash_var.set(ip_hash),
        user_agent_var.set(user_agent),
        endpoint_var.set(endpoint),
        method_var.set(method),
    ]


def reset_request_context(tokens: list[Token[str | None]]) -> None:
    """Restaura os valores anteriores, na ordem inversa."""
    for token in reversed(tokens):
        token.var.reset(token)


@contextmanager
def bind_user(user_id: uuid.UUID | None) -> Iterator[None]:
    """Associa o usuário autenticado ao contexto corrente."""
    token = user_id_var.set(user_id)
    try:
        yield
    finally:
        user_id_var.reset(token)


def current_request_id() -> str | None:
    return request_id_var.get()


def current_correlation_id() -> str | None:
    return correlation_id_var.get()


def current_user_id() -> uuid.UUID | None:
    return user_id_var.get()


def current_ip() -> str | None:
    return ip_var.get()


def current_ip_hash() -> str | None:
    return ip_hash_var.get()


def current_user_agent() -> str | None:
    return user_agent_var.get()


def current_endpoint() -> str | None:
    return endpoint_var.get()


def normalize_ip(raw: str | None) -> str | None:
    """Normaliza um IP já resolvido pela borda; ``None`` se inválido."""
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return None


def request_ip(request: Request) -> str | None:
    """IP do cliente resolvido na borda (SEC-002).

    O uvicorn só confia no ``X-Forwarded-For`` reescrito pelo Caddy local
    (``--forwarded-allow-ips 127.0.0.1``), portanto ``request.client.host`` já
    é o IP do cliente. Headers enviados pelo cliente nunca são lidos aqui.
    """
    return normalize_ip(request.client.host if request.client else None)


def request_ip_hash(request: Request, settings: Settings) -> str | None:
    """Hash do peer imediato resolvido pela borda.

    Mantém o contrato anterior de hash (inclusive o host sintético do
    ``TestClient``); o IP completo só é registrado quando é um IP válido.
    """
    raw = request.client.host if request.client else None
    if not raw:
        return None
    return hash_ip(raw.strip(), settings.phone_hash_secret.get_secret_value())
