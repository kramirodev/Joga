"""Limpeza provisória de mensagens, convites, Outbox e tokens de push."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.outbox.models import OutboxEvent
from app.modules.social.models import DevicePushToken, LobbyInvite

MESSAGE_RETENTION_DAYS = 730
INVITE_RETENTION_DAYS = 90
OUTBOX_RETENTION_DAYS = 30
PUSH_TOKEN_RETENTION_DAYS = 90


@dataclass(frozen=True)
class CommunicationCleanupResult:
    messages: int
    invites: int
    outbox_events: int
    push_tokens: int


def cleanup_communication(
    session: Session,
    *,
    message_days: int = MESSAGE_RETENTION_DAYS,
    invite_days: int = INVITE_RETENTION_DAYS,
    outbox_days: int = OUTBOX_RETENTION_DAYS,
    push_token_days: int = PUSH_TOKEN_RETENTION_DAYS,
    now: datetime | None = None,
) -> CommunicationCleanupResult:
    if min(message_days, invite_days, outbox_days, push_token_days) < 0:
        raise ValueError("prazos de retenção não podem ser negativos")

    moment = ensure_utc(now or utcnow())
    message_cutoff = moment - timedelta(days=message_days)
    invite_cutoff = moment - timedelta(days=invite_days)
    outbox_cutoff = moment - timedelta(days=outbox_days)
    push_cutoff = moment - timedelta(days=push_token_days)

    messages = _rowcount(
        session,
        delete(LobbyMessage).where(LobbyMessage.created_at < message_cutoff),
    )
    invites = _rowcount(
        session,
        delete(LobbyInvite).where(
            LobbyInvite.status.in_(("DECLINED", "EXPIRED", "CANCELLED")),
            func.coalesce(LobbyInvite.responded_at, LobbyInvite.created_at) < invite_cutoff,
        ),
    )
    outbox_events = _rowcount(
        session,
        delete(OutboxEvent).where(
            OutboxEvent.status.in_(("DISPATCHED", "FAILED")),
            func.coalesce(OutboxEvent.dispatched_at, OutboxEvent.created_at) < outbox_cutoff,
        ),
    )
    push_tokens = _rowcount(
        session,
        delete(DevicePushToken).where(
            DevicePushToken.revoked_at.is_not(None),
            DevicePushToken.revoked_at < push_cutoff,
        ),
    )

    session.flush()
    return CommunicationCleanupResult(
        messages=messages,
        invites=invites,
        outbox_events=outbox_events,
        push_tokens=push_tokens,
    )


def _rowcount(session: Session, statement: Any) -> int:
    result = cast(CursorResult[Any], session.execute(statement))
    return int(result.rowcount or 0)
