"""Alertas de segurança transacionais vinculados à credencial primária."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.email.models import UserEmail


def primary_email(session: Session, user_id: uuid.UUID) -> str | None:
    """Endereço primário ativo do usuário, quando existir."""
    return session.scalar(
        select(UserEmail.email_normalized).where(
            UserEmail.user_id == user_id,
            UserEmail.released_at.is_(None),
            UserEmail.is_primary.is_(True),
        )
    )


def queue_security_alert(
    session: Session,
    deliveries: EmailDeliveryService,
    *,
    user_id: uuid.UUID,
    reference: str,
    device_label: str | None = None,
) -> None:
    """Agenda um alerta sem interromper o fluxo de segurança que o originou."""
    email = primary_email(session, user_id)
    if email is None:
        return
    try:
        deliveries.enqueue(
            "security_alert",
            to=email,
            user_id=user_id,
            reference=reference,
            context={
                "occurred_at": datetime.now().astimezone().strftime("%d/%m/%Y %H:%M UTC"),
                "device_label": device_label,
            },
        )
    except EmailBudgetExhausted:
        return


__all__ = ["primary_email", "queue_security_alert"]
