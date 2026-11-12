"""Trust Factor interno: eventos, recuperação e restrição ranqueada (ADR 0041)."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.ratings.models import TrustAccount, TrustEvent

NEGATIVE_EVENT_TYPES = frozenset({"no_show", "cancel_after_confirmation", "cancel_before_payment"})
NO_SHOW_PENALTY = 30
CANCEL_AFTER_CONFIRMATION_PENALTY = 7
CANCEL_BEFORE_PAYMENT_PENALTY = 2
MATCH_COMPLETED_MAX_RECOVERY = 6
RECOVERY_RATE = 0.2
RECURRENCE_STEP = 0.5
RECURRENCE_CAP = 2.0
WINDOW = timedelta(days=30)
SHORT_RESTRICTION_DAYS = 7
LONG_RESTRICTION_DAYS = 30


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TrustService:
    """Aplica o Trust Factor interno; o score nunca é exposto ao jogador."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def apply_event(
        self,
        user_id: uuid.UUID,
        event_type: str,
        *,
        match_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> TrustEvent:
        moment = ensure_utc(now or utcnow())
        account = self._account_for(user_id, moment)
        score_before = account.score

        if event_type in NEGATIVE_EVENT_TYPES:
            base = {
                "no_show": NO_SHOW_PENALTY,
                "cancel_after_confirmation": CANCEL_AFTER_CONFIRMATION_PENALTY,
                "cancel_before_payment": CANCEL_BEFORE_PAYMENT_PENALTY,
            }[event_type]
            prior = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(TrustEvent)
                    .where(
                        TrustEvent.user_id == user_id,
                        TrustEvent.event_type.in_(NEGATIVE_EVENT_TYPES),
                        TrustEvent.created_at >= moment - WINDOW,
                    )
                )
                or 0
            )
            multiplier = min(RECURRENCE_CAP, 1.0 + RECURRENCE_STEP * prior)
            delta = -math.ceil(base * multiplier)
            severity = {"no_show": 5, "cancel_after_confirmation": 3, "cancel_before_payment": 1}[
                event_type
            ]
        elif event_type == "match_completed":
            gap = max(0, 100 - score_before)
            recovery = (
                min(MATCH_COMPLETED_MAX_RECOVERY, max(1, math.ceil(gap * RECOVERY_RATE)))
                if gap > 0
                else 0
            )
            multiplier = 1.0
            delta = min(recovery, gap)
            severity = 0
        else:
            raise ValueError("evento de confiança desconhecido")

        score_after = min(100, max(0, score_before + delta))
        account.score = score_after
        account.updated_at = moment
        event_details = {
            "delta": delta,
            "score_before": score_before,
            "score_after": score_after,
            "multiplier": multiplier,
        }
        if details:
            event_details.update(details)
        event = TrustEvent(
            user_id=user_id,
            match_id=match_id,
            event_type=event_type,
            severity=severity,
            details=event_details,
            created_at=moment,
        )
        self.session.add(event)
        self._apply_restriction(account, user_id, moment)
        self.session.flush()
        return event

    def is_ranked_restricted(
        self,
        user_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> bool:
        account = self.session.get(TrustAccount, user_id)
        if account is None or account.ranked_restricted_until is None:
            return False
        return _aware(account.ranked_restricted_until) > ensure_utc(now or utcnow())

    def _apply_restriction(
        self,
        account: TrustAccount,
        user_id: uuid.UUID,
        moment: datetime,
    ) -> None:
        counts = {
            event_type: int(count)
            for event_type, count in self.session.execute(
                select(TrustEvent.event_type, func.count())
                .where(
                    TrustEvent.user_id == user_id,
                    TrustEvent.event_type.in_(NEGATIVE_EVENT_TYPES),
                    TrustEvent.created_at >= moment - WINDOW,
                )
                .group_by(TrustEvent.event_type)
            ).all()
        }
        no_shows = counts.get("no_show", 0)
        after_confirmation = counts.get("cancel_after_confirmation", 0)
        if no_shows >= 3 or after_confirmation >= 4:
            days = LONG_RESTRICTION_DAYS
        elif no_shows >= 2 or after_confirmation >= 3:
            days = SHORT_RESTRICTION_DAYS
        else:
            return
        candidate = moment + timedelta(days=days)
        current = (
            _aware(account.ranked_restricted_until)
            if account.ranked_restricted_until is not None
            else moment
        )
        account.ranked_restricted_until = max(current, candidate)

    def _account_for(self, user_id: uuid.UUID, moment: datetime) -> TrustAccount:
        account = self.session.get(TrustAccount, user_id, with_for_update=True)
        if account is not None:
            return account
        account = TrustAccount(user_id=user_id, score=100, updated_at=moment)
        try:
            with self.session.begin_nested():
                self.session.add(account)
                self.session.flush()
        except IntegrityError:
            account = self.session.get(TrustAccount, user_id, with_for_update=True)
            if account is None:
                raise
        return account


__all__ = ["TrustService"]
