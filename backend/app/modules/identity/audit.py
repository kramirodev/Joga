"""Registro append-only de ações administrativas."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.identity.models import AuditLog


def record_audit(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None,
    organization_id: uuid.UUID | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Adiciona um evento de auditoria na transação corrente.

    O chamador é responsável pelo commit. Não há atualização nem remoção:
    correções devem ser registradas como novos eventos.
    """

    event = AuditLog(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        reason=reason,
        details=details,
    )
    session.add(event)
    return event
