"""Hashes de contexto da requisição; nunca IP ou user-agent em claro."""

from __future__ import annotations

import hashlib

from fastapi import Request

from app.core.config import Settings
from app.modules.identity.phone import hash_ip


def request_ip_hash(request: Request, settings: Settings) -> str | None:
    ip = request.client.host if request.client else None
    if ip is None:
        return None
    return hash_ip(ip, settings.phone_hash_secret.get_secret_value())


def request_user_agent_hash(request: Request) -> str | None:
    agent = request.headers.get("user-agent")
    if not agent:
        return None
    return hashlib.sha256(agent.encode("utf-8", errors="replace")).hexdigest()
