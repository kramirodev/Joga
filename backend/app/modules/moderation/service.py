"""Denúncias, revisão humana e medidas reversíveis (Fase 17A)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.chat.models import LobbyMessage
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.moderation.classifier import DEFAULT_CLASSIFIER, ModerationClassifier
from app.modules.moderation.models import (
    REPORT_CATEGORIES,
    ModerationAction,
    ModerationAppeal,
    ModerationOperator,
    ModerationReport,
)
from app.modules.notifications.service import NotificationService
from app.modules.ratings.models import TrustAccount

MAX_CONTEXT_MESSAGES = 5
REPORT_WINDOW = timedelta(days=1)
PRIORITY_WINDOW = timedelta(days=30)
MAX_REASON = 1000
DECISIONS = frozenset({"DISMISS", "WARN", "RESTRICT_RANKED", "SUSPEND_TEMP"})
APPEAL_DECISIONS = frozenset({"ACCEPTED", "REJECTED"})


class ModerationError(Exception):
    """Erro base de moderação."""


class ReportInvalid(ModerationError):
    """Dados da denúncia inválidos."""


class ReportForbidden(ModerationError):
    """Denunciante ou alvo fora do lobby."""


class ReportConflict(ModerationError):
    """Denúncia duplicada ou limite de frequência."""


class ReportNotFound(ModerationError):
    """Denúncia inexistente."""


class OperatorNotAuthorized(ModerationError):
    """Operador não autorizado a decidir."""


class ActionNotFound(ModerationError):
    """Medida inexistente."""


class OperatorNotFound(ModerationError):
    """Conta que se pretende promover a operador não existe."""


class AppealConflict(ModerationError):
    """Recurso duplicado ou em estado inválido."""


def _clean_text(value: str, *, label: str, max_length: int) -> str:
    cleaned = " ".join(value.split()).strip()
    if not 1 <= len(cleaned) <= max_length:
        raise ReportInvalid(f"{label}_invalid")
    return cleaned


class ModerationService:
    """Fluxo humano: denúncia → triagem → revisão → medida → recurso."""

    def __init__(
        self,
        session: Session,
        *,
        classifier: ModerationClassifier | None = None,
    ) -> None:
        self.session = session
        self.classifier = classifier or DEFAULT_CLASSIFIER

    def create_report(
        self,
        reporter_id: uuid.UUID,
        *,
        target_user_id: uuid.UUID,
        lobby_id: uuid.UUID,
        category: str,
        description: str,
        message_ids: list[uuid.UUID] | None = None,
        now: datetime | None = None,
    ) -> ModerationReport:
        if reporter_id == target_user_id:
            raise ReportInvalid("self_report")
        if category not in REPORT_CATEGORIES:
            raise ReportInvalid("category_invalid")
        text = _clean_text(description, label="description", max_length=2000)
        moment = ensure_utc(now or utcnow())
        lobby = self.session.get(Lobby, lobby_id)
        if lobby is None:
            raise ReportInvalid("lobby_not_found")
        participants = {
            item
            for item in self.session.scalars(
                select(LobbyParticipant.user_id).where(LobbyParticipant.lobby_id == lobby.id)
            ).all()
        }
        if reporter_id not in participants or target_user_id not in participants:
            raise ReportForbidden

        selected_ids = list(dict.fromkeys(message_ids or []))
        if len(selected_ids) > MAX_CONTEXT_MESSAGES:
            raise ReportInvalid("context_too_large")
        messages: list[LobbyMessage] = []
        if selected_ids:
            messages = list(
                self.session.scalars(
                    select(LobbyMessage)
                    .where(
                        LobbyMessage.id.in_(selected_ids),
                        LobbyMessage.lobby_id == lobby.id,
                    )
                    .order_by(LobbyMessage.created_at)
                ).all()
            )
            if len(messages) != len(selected_ids) or any(
                message.sender_id != target_user_id for message in messages
            ):
                raise ReportInvalid("context_invalid")

        recent = int(
            self.session.scalar(
                select(func.count())
                .select_from(ModerationReport)
                .where(
                    ModerationReport.reporter_id == reporter_id,
                    ModerationReport.created_at >= moment - REPORT_WINDOW,
                )
            )
            or 0
        )
        if recent >= get_settings().moderation_max_reports_per_day:
            raise ReportConflict("report_rate_limited")

        dismissed = list(
            self.session.scalars(
                select(ModerationReport.reviewed_at)
                .where(
                    ModerationReport.reporter_id == reporter_id,
                    ModerationReport.status == "DISMISSED",
                    ModerationReport.reviewed_at.is_not(None),
                    ModerationReport.reviewed_at >= moment - PRIORITY_WINDOW,
                )
                .order_by(ModerationReport.reviewed_at.desc())
            ).all()
        )
        if dismissed:
            settings = get_settings()
            raw_last = dismissed[0]
            assert raw_last is not None
            last = ensure_utc(raw_last)
            cooldown = timedelta(days=settings.moderation_false_report_cooldown_days)
            if (
                len(dismissed) >= settings.moderation_false_report_threshold
                and last + cooldown > moment
            ):
                raise ReportConflict("reporter_cooldown")

        duplicate = self.session.scalar(
            select(ModerationReport).where(
                ModerationReport.reporter_id == reporter_id,
                ModerationReport.target_user_id == target_user_id,
                ModerationReport.lobby_id == lobby.id,
                ModerationReport.status.in_(("OPEN", "IN_REVIEW", "APPEALED")),
            )
        )
        if duplicate is not None:
            raise ReportConflict("report_already_open")

        prior_reports = int(
            self.session.scalar(
                select(func.count())
                .select_from(ModerationReport)
                .where(
                    ModerationReport.target_user_id == target_user_id,
                    ModerationReport.created_at >= moment - PRIORITY_WINDOW,
                )
            )
            or 0
        )
        classification = self.classifier.classify(
            category=category,
            prior_reports=prior_reports,
            context_messages=len(messages),
            description_length=len(text),
        )
        report = ModerationReport(
            reporter_id=reporter_id,
            target_user_id=target_user_id,
            lobby_id=lobby.id,
            category=category,
            description=text,
            context=[
                {
                    "id": str(message.id),
                    "sender_id": str(message.sender_id),
                    "body": message.body,
                    "created_at": ensure_utc(message.created_at).isoformat(),
                }
                for message in messages
            ],
            status="OPEN",
            priority=classification.priority,
            severity=classification.severity,
            classifier_version="rules_v1",
            classifier_signals=classification.signals,
            created_at=moment,
        )
        self.session.add(report)
        self.session.flush()
        record_audit(
            self.session,
            actor_user_id=reporter_id,
            action="moderation.report_created",
            resource_type="moderation_report",
            resource_id=report.id,
            details={
                "target_user_id": str(target_user_id),
                "lobby_id": str(lobby.id),
                "category": category,
                "priority": report.priority,
                "severity": report.severity,
            },
        )
        self._notify_operators(report, moment)
        self.session.flush()
        return report

    def list_my_reports(
        self,
        reporter_id: uuid.UUID,
        *,
        limit: int = 30,
        offset: int = 0,
    ) -> list[ModerationReport]:
        return list(
            self.session.scalars(
                select(ModerationReport)
                .where(ModerationReport.reporter_id == reporter_id)
                .order_by(ModerationReport.created_at.desc(), ModerationReport.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def queue(
        self,
        *,
        status_filter: str = "OPEN",
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModerationReport]:
        return list(
            self.session.scalars(
                select(ModerationReport)
                .where(ModerationReport.status == status_filter)
                .order_by(
                    ModerationReport.priority.desc(),
                    ModerationReport.created_at,
                    ModerationReport.id,
                )
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def get_report(self, report_id: uuid.UUID) -> ModerationReport:
        report = self.session.get(ModerationReport, report_id)
        if report is None:
            raise ReportNotFound
        return report

    def stats(self) -> dict[str, int]:
        rows = self.session.execute(
            select(ModerationReport.status, func.count()).group_by(ModerationReport.status)
        ).all()
        counts = {str(status): int(count) for status, count in rows}
        high = int(
            self.session.scalar(
                select(func.count())
                .select_from(ModerationReport)
                .where(
                    ModerationReport.status == "OPEN",
                    ModerationReport.severity == "HIGH",
                )
            )
            or 0
        )
        return {
            "open": counts.get("OPEN", 0),
            "in_review": counts.get("IN_REVIEW", 0),
            "appealed": counts.get("APPEALED", 0),
            "high_priority": high,
        }

    def list_appeals(self, *, status_filter: str = "OPEN") -> list[ModerationAppeal]:
        return list(
            self.session.scalars(
                select(ModerationAppeal)
                .where(ModerationAppeal.status == status_filter)
                .order_by(ModerationAppeal.created_at)
            ).all()
        )

    def operator_role(self, user_id: uuid.UUID) -> str | None:
        row = self.session.get(ModerationOperator, user_id)
        if row is not None and row.active:
            return row.role
        if str(user_id) in get_settings().moderation_admin_ids:
            return "ADMIN"
        return None

    def list_operators(self) -> list[ModerationOperator]:
        return list(
            self.session.scalars(
                select(ModerationOperator).order_by(
                    ModerationOperator.created_at,
                    ModerationOperator.user_id,
                )
            ).all()
        )

    def add_operator(
        self,
        actor_user_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        role: str = "MODERATOR",
    ) -> ModerationOperator:
        if role not in {"ADMIN", "MODERATOR"}:
            raise ReportInvalid("role_invalid")
        if self.session.get(User, user_id) is None:
            raise OperatorNotFound
        row = self.session.get(ModerationOperator, user_id)
        if row is None:
            row = ModerationOperator(
                user_id=user_id,
                role=role,
                active=True,
                created_by=actor_user_id,
            )
            self.session.add(row)
        else:
            row.role = role
            row.active = True
            row.deactivated_at = None
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="moderation.operator_upserted",
            resource_type="moderation_operator",
            resource_id=user_id,
            details={"role": role},
        )
        self.session.flush()
        return row

    def deactivate_operator(self, actor_user_id: uuid.UUID, user_id: uuid.UUID) -> None:
        row = self.session.get(ModerationOperator, user_id)
        if row is None:
            raise ActionNotFound
        row.active = False
        row.deactivated_at = ensure_utc(utcnow())
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="moderation.operator_deactivated",
            resource_type="moderation_operator",
            resource_id=user_id,
            details={},
        )
        self.session.flush()

    def _notify_operators(self, report: ModerationReport, moment: datetime) -> None:
        operator_ids = set(
            self.session.scalars(
                select(ModerationOperator.user_id).where(ModerationOperator.active.is_(True))
            ).all()
        )
        for raw in get_settings().moderation_admin_ids:
            try:
                operator_ids.add(uuid.UUID(raw))
            except ValueError:
                continue
        if not operator_ids:
            return
        NotificationService(self.session).create_many(
            list(operator_ids),
            kind="moderation_report",
            title="Nova denúncia",
            body=(f"{report.category} · {report.severity} · prioridade {report.priority}"),
            idempotency_key_prefix=f"moderation_report:{report.id}",
            data={
                "report_id": str(report.id),
                "severity": report.severity,
                "priority": report.priority,
            },
            now=moment,
        )

    def review(
        self,
        report_id: uuid.UUID,
        *,
        operator: str,
        decision: str,
        reason: str,
        days: int = 7,
        authorized_operators: frozenset[str] | None = None,
        now: datetime | None = None,
    ) -> tuple[ModerationReport, ModerationAction | None]:
        allowed = (
            authorized_operators
            if authorized_operators is not None
            else get_settings().moderation_operator_ids
        )
        if operator not in allowed:
            raise OperatorNotAuthorized
        if decision not in DECISIONS:
            raise ReportInvalid("decision_invalid")
        cleaned = _clean_text(reason, label="reason", max_length=MAX_REASON)
        if decision == "RESTRICT_RANKED" and not 1 <= days <= 90:
            raise ReportInvalid("days_invalid")
        if decision == "SUSPEND_TEMP" and not 1 <= days <= 30:
            raise ReportInvalid("days_invalid")
        moment = ensure_utc(now or utcnow())
        report = self.session.scalar(
            select(ModerationReport).where(ModerationReport.id == report_id).with_for_update()
        )
        if report is None:
            raise ReportNotFound
        if report.status not in {"OPEN", "IN_REVIEW"}:
            raise ReportConflict("report_not_open")

        action: ModerationAction | None = None
        if decision == "DISMISS":
            report.status = "DISMISSED"
        else:
            action_type = {
                "WARN": "WARNING",
                "RESTRICT_RANKED": "RESTRICT_RANKED",
                "SUSPEND_TEMP": "SUSPEND_TEMP",
            }[decision]
            action = ModerationAction(
                report_id=report.id,
                target_user_id=report.target_user_id,
                action_type=action_type,
                status="ACTIVE",
                starts_at=moment,
                ends_at=(moment + timedelta(days=days) if action_type != "WARNING" else None),
                reason=cleaned,
                operator=operator,
            )
            self.session.add(action)
            self.session.flush()
            if action_type == "RESTRICT_RANKED":
                self._restrict_ranked(report.target_user_id, action.ends_at, moment)
            if action_type == "SUSPEND_TEMP":
                self._suspend_user(report.target_user_id, action.ends_at, moment)
            report.status = "RESOLVED"
            NotificationService(self.session).create(
                user_id=report.target_user_id,
                kind="moderation_action",
                title="Medida de moderação",
                body="Uma medida foi aplicada à sua conta. Abra os detalhes para recorrer.",
                idempotency_key=f"moderation_action:{action.id}:{report.target_user_id}",
                data={"action_id": str(action.id)},
                now=moment,
            )
        report.reviewed_at = moment
        report.reviewed_by = operator
        report.decision_reason = cleaned
        record_audit(
            self.session,
            actor_user_id=None,
            action="moderation.report_reviewed",
            resource_type="moderation_report",
            resource_id=report.id,
            reason=cleaned,
            details={
                "operator": operator,
                "decision": decision,
                "action_id": str(action.id) if action is not None else None,
            },
        )
        self.session.flush()
        return report, action

    def list_actions(self, user_id: uuid.UUID, *, limit: int = 30) -> list[ModerationAction]:
        return list(
            self.session.scalars(
                select(ModerationAction)
                .where(ModerationAction.target_user_id == user_id)
                .order_by(ModerationAction.created_at.desc())
                .limit(limit)
            ).all()
        )

    def appeal(
        self,
        action_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        reason: str,
        now: datetime | None = None,
    ) -> ModerationAppeal:
        action = self.session.get(ModerationAction, action_id)
        if action is None or action.target_user_id != user_id:
            raise ActionNotFound
        if action.status != "ACTIVE":
            raise AppealConflict("action_not_active")
        existing = self.session.scalar(
            select(ModerationAppeal).where(
                ModerationAppeal.action_id == action.id,
                ModerationAppeal.user_id == user_id,
            )
        )
        if existing is not None:
            raise AppealConflict("appeal_already_exists")
        cleaned = _clean_text(reason, label="reason", max_length=MAX_REASON)
        moment = ensure_utc(now or utcnow())
        appeal = ModerationAppeal(
            action_id=action.id,
            user_id=user_id,
            reason=cleaned,
            status="OPEN",
            created_at=moment,
        )
        self.session.add(appeal)
        report = self.session.get(ModerationReport, action.report_id)
        if report is not None:
            report.status = "APPEALED"
        record_audit(
            self.session,
            actor_user_id=user_id,
            action="moderation.appeal_created",
            resource_type="moderation_appeal",
            resource_id=appeal.id,
            details={"action_id": str(action.id)},
        )
        self.session.flush()
        return appeal

    def review_appeal(
        self,
        appeal_id: uuid.UUID,
        *,
        operator: str,
        decision: str,
        reason: str,
        authorized_operators: frozenset[str] | None = None,
        now: datetime | None = None,
    ) -> ModerationAppeal:
        allowed = (
            authorized_operators
            if authorized_operators is not None
            else get_settings().moderation_operator_ids
        )
        if operator not in allowed:
            raise OperatorNotAuthorized
        if decision not in APPEAL_DECISIONS:
            raise ReportInvalid("decision_invalid")
        cleaned = _clean_text(reason, label="reason", max_length=MAX_REASON)
        moment = ensure_utc(now or utcnow())
        appeal = self.session.scalar(
            select(ModerationAppeal).where(ModerationAppeal.id == appeal_id).with_for_update()
        )
        if appeal is None:
            raise ReportNotFound
        if appeal.status != "OPEN":
            raise AppealConflict("appeal_not_open")
        appeal.status = decision
        appeal.decided_at = moment
        appeal.decided_by = operator
        appeal.decision_reason = cleaned
        action = self.session.get(ModerationAction, appeal.action_id)
        if decision == "ACCEPTED" and action is not None:
            self.revoke_action(action.id, operator=operator, reason=cleaned, now=moment)
        if action is not None:
            report = self.session.get(ModerationReport, action.report_id)
            if report is not None:
                report.status = "RESOLVED"
        record_audit(
            self.session,
            actor_user_id=None,
            action="moderation.appeal_reviewed",
            resource_type="moderation_appeal",
            resource_id=appeal.id,
            reason=cleaned,
            details={"operator": operator, "decision": decision},
        )
        self.session.flush()
        return appeal

    def revoke_action(
        self,
        action_id: uuid.UUID,
        *,
        operator: str,
        reason: str,
        now: datetime | None = None,
    ) -> ModerationAction:
        action = self.session.scalar(
            select(ModerationAction).where(ModerationAction.id == action_id).with_for_update()
        )
        if action is None:
            raise ActionNotFound
        if action.status != "ACTIVE":
            return action
        moment = ensure_utc(now or utcnow())
        action.status = "REVOKED"
        action.revoked_at = moment
        action.revoke_reason = _clean_text(reason, label="reason", max_length=MAX_REASON)
        if action.action_type == "RESTRICT_RANKED":
            account = self.session.get(TrustAccount, action.target_user_id, with_for_update=True)
            if account is not None and account.ranked_restricted_until is not None:
                if ensure_utc(account.ranked_restricted_until) > moment:
                    account.ranked_restricted_until = moment
        if action.action_type == "SUSPEND_TEMP":
            user = self.session.get(User, action.target_user_id, with_for_update=True)
            if user is not None and user.status == "suspended":
                user.status = "active"
                user.suspended_until = None
                user.updated_at = moment
        record_audit(
            self.session,
            actor_user_id=None,
            action="moderation.action_revoked",
            resource_type="moderation_action",
            resource_id=action.id,
            reason=action.revoke_reason,
            details={"operator": operator, "action_type": action.action_type},
        )
        self.session.flush()
        return action

    def _restrict_ranked(
        self,
        user_id: uuid.UUID,
        ends_at: datetime | None,
        moment: datetime,
    ) -> None:
        if ends_at is None:
            raise ReportInvalid("ends_at_required")
        account = self.session.get(TrustAccount, user_id, with_for_update=True)
        if account is None:
            account = TrustAccount(user_id=user_id, score=100, updated_at=moment)
            self.session.add(account)
            self.session.flush()
        current = (
            ensure_utc(account.ranked_restricted_until)
            if account.ranked_restricted_until is not None
            else moment
        )
        account.ranked_restricted_until = max(current, ends_at)
        account.updated_at = moment

    def _suspend_user(
        self,
        user_id: uuid.UUID,
        ends_at: datetime | None,
        moment: datetime,
    ) -> None:
        if ends_at is None:
            raise ReportInvalid("ends_at_required")
        user = self.session.get(User, user_id, with_for_update=True)
        if user is None:
            raise ReportInvalid("user_not_found")
        user.status = "suspended"
        user.suspended_until = max(
            ensure_utc(user.suspended_until) if user.suspended_until is not None else moment,
            ends_at,
        )
        user.updated_at = moment


__all__ = [
    "ActionNotFound",
    "AppealConflict",
    "ModerationError",
    "ModerationService",
    "OperatorNotAuthorized",
    "OperatorNotFound",
    "ReportConflict",
    "ReportForbidden",
    "ReportInvalid",
    "ReportNotFound",
]
