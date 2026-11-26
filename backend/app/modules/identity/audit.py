"""Registro append-only de ações administrativas."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core import request_context
from app.modules.identity.models import AuditLog
from app.modules.observability.redaction import (
    sanitize_details,
    sanitize_message,
    sanitize_user_agent,
)


def record_audit(
    session: Session,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None,
    organization_id: uuid.UUID | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    result: str | None = "success",
) -> AuditLog:
    """Adiciona um evento de auditoria na transação corrente.

    O chamador é responsável pelo commit. Não há atualização nem remoção:
    correções devem ser registradas como novos eventos. O contexto da
    requisição (request_id, IP resolvido na borda, endpoint e user-agent)
    é preenchido automaticamente quando disponível.
    """

    event = AuditLog(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        reason=sanitize_message(reason),
        ip=request_context.current_ip(),
        ip_hash=request_context.current_ip_hash(),
        request_id=request_context.current_request_id(),
        endpoint=request_context.current_endpoint(),
        user_agent=sanitize_user_agent(request_context.current_user_agent()),
        result=result,
        details=sanitize_details(details),
    )
    session.add(event)
    return event
