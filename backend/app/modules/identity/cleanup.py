"""Limpeza de dados efêmeros de identidade (desafios, sessões e eventos)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import (
    PasskeyChallenge,
    PhoneChallenge,
    SecurityEvent,
)
from app.modules.identity.models import Session as SessionRecord


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


@dataclass(frozen=True)
class CleanupResult:
    phone_challenges: int
    passkey_challenges: int
    sessions: int
    security_events: int


def cleanup_identity(
    session: Session,
    *,
    now: datetime | None = None,
    challenge_retention_days: int = 1,
    session_retention_days: int = 30,
    event_retention_days: int = 90,
) -> CleanupResult:
    """Remove registros antigos; não altera usuários, telefones ou credenciais."""
    for name, value in (
        ("challenge_retention_days", challenge_retention_days),
        ("session_retention_days", session_retention_days),
        ("event_retention_days", event_retention_days),
    ):
        if value <= 0:
            raise ValueError(f"{name} deve ser positivo")

    moment = ensure_utc(now or utcnow())
    challenge_cutoff = moment - timedelta(days=challenge_retention_days)
    session_cutoff = moment - timedelta(days=session_retention_days)
    event_cutoff = moment - timedelta(days=event_retention_days)

    phone_challenges = _rowcount(
        session.execute(delete(PhoneChallenge).where(PhoneChallenge.expires_at < challenge_cutoff))
    )
    passkey_challenges = _rowcount(
        session.execute(
            delete(PasskeyChallenge).where(PasskeyChallenge.expires_at < challenge_cutoff)
        )
    )
    sessions = _rowcount(
        session.execute(
            delete(SessionRecord).where(
                or_(
                    SessionRecord.expires_at < session_cutoff,
                    and_(
                        SessionRecord.revoked_at.is_not(None),
                        SessionRecord.revoked_at < session_cutoff,
                    ),
                )
            )
        )
    )
    security_events = _rowcount(
        session.execute(delete(SecurityEvent).where(SecurityEvent.created_at < event_cutoff))
    )

    return CleanupResult(
        phone_challenges=phone_challenges,
        passkey_challenges=passkey_challenges,
        sessions=sessions,
        security_events=security_events,
    )
