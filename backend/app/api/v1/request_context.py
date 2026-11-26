"""Hashes e IP de contexto da requisição; nunca cadeia de proxy própria."""

from __future__ import annotations

import hashlib

from fastapi import Request

from app.core.request_context import normalize_ip, request_ip, request_ip_hash

__all__ = ["normalize_ip", "request_ip", "request_ip_hash", "request_user_agent_hash"]


def request_user_agent_hash(request: Request) -> str | None:
    agent = request.headers.get("user-agent")
    if not agent:
        return None
    return hashlib.sha256(agent.encode("utf-8", errors="replace")).hexdigest()
