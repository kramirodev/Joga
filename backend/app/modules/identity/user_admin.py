"""Administração de usuários por `platform_admin` (auditada e mínima).

O admin nunca lê senha/hash/OTP/CPF em claro, nunca altera MMR, ledger,
tickets ou resultado. Toda escrita exige motivo e gera evento append-only em
`audit_logs`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.text import escape_like, normalize_display_name
from app.modules.email.addresses import normalize_email
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.email.models import UserEmail
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.email_challenges import EmailChallengeService
from app.modules.identity.models import AuditLog, User, UserPassword
from app.modules.identity.otp import ChallengePurpose
from app.modules.identity.passwords import PasswordService
from app.modules.identity.sessions import SessionService
from app.modules.identity.tags import next_available_tag
from app.modules.profile.cpf import mask_cpf
from app.modules.profile.models import UserProfile

USER_STATUSES = ("pending", "active", "suspended", "deleted")


class AdminUserError(Exception):
    """Erro base da administração de usuários."""


class AdminUserNotFound(AdminUserError):
    """Usuário inexistente."""


class AdminEmailConflict(AdminUserError):
    """E-mail já vinculado a outra conta."""


class AdminEmailUnchanged(AdminUserError):
    """O novo e-mail é igual ao atual."""


class InvalidAdminUser(AdminUserError):
    """Dados ou motivo inválidos."""


class ReasonRequired(InvalidAdminUser):
    """Toda escrita administrativa exige motivo não vazio."""


@dataclass(frozen=True)
class AdminUserView:
    id: uuid.UUID
    status: str
    email: str | None
    display_name: str | None
    email_verified: bool
    cpf_masked: str | None
    suspended_until: datetime | None
    created_at: datetime


def require_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip()
    if not cleaned:
        raise ReasonRequired
    if len(cleaned) > 500:
        raise InvalidAdminUser
    return cleaned


def _primary_email(session: Session, user_id: uuid.UUID) -> UserEmail | None:
    return session.scalar(
        select(UserEmail).where(
            UserEmail.user_id == user_id,
            UserEmail.released_at.is_(None),
            UserEmail.is_primary.is_(True),
        )
    )


def _active_email(session: Session, normalized: str) -> UserEmail | None:
    return session.scalar(
        select(UserEmail).where(
            UserEmail.email_normalized == normalized,
            UserEmail.released_at.is_(None),
        )
    )


def _view(session: Session, user: User) -> AdminUserView:
    profile = session.get(UserProfile, user.id)
    credential = _primary_email(session, user.id)
    return AdminUserView(
        id=user.id,
        status=user.status,
        email=credential.email_normalized if credential is not None else None,
        display_name=profile.display_name if profile is not None else None,
        email_verified=bool(credential is not None and credential.verified_at is not None),
        cpf_masked=mask_cpf(profile.cpf_last2) if profile is not None else None,
        suspended_until=ensure_utc(user.suspended_until) if user.suspended_until else None,
        created_at=ensure_utc(user.created_at),
    )


def get_user(session: Session, user_id: uuid.UUID) -> AdminUserView:
    user = session.get(User, user_id)
    if user is None:
        raise AdminUserNotFound
    return _view(session, user)


def search_users(
    session: Session,
    *,
    search: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AdminUserView], int]:
    if page < 1 or page_size < 1 or page_size > 50:
        raise InvalidAdminUser
    if status is not None and status not in USER_STATUSES:
        raise InvalidAdminUser

    conditions = []
    if search:
        term = f"%{escape_like(search.strip())}%"
        conditions.append(
            or_(
                UserEmail.email_normalized.ilike(term, escape="\\"),
                UserProfile.display_name.ilike(term, escape="\\"),
            )
        )
    if status:
        conditions.append(User.status == status)

    base = (
        select(User)
        .outerjoin(
            UserEmail,
            and_(UserEmail.user_id == User.id, UserEmail.released_at.is_(None)),
        )
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(*conditions)
        .distinct()
    )
    total = int(
        session.scalar(
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .outerjoin(
                UserEmail,
                and_(UserEmail.user_id == User.id, UserEmail.released_at.is_(None)),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(*conditions)
        )
        or 0
    )
    rows = session.scalars(
        base.order_by(User.created_at.desc(), User.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return [_view(session, row) for row in rows], total


def create_user(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str | None,
    verify_email: bool,
    passwords: PasswordService,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> AdminUserView:
    cleaned_reason = require_reason(reason)
    normalized = normalize_email(email)
    passwords.validate(password, normalized)
    if _active_email(session, normalized) is not None:
        raise AdminEmailConflict
    clean_name = normalize_display_name(display_name)

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        status="active",
        tag=next_available_tag(session, user_id),
    )
    session.add(user)
    try:
        session.flush()
        session.add(
            UserEmail(
                user_id=user.id,
                email_normalized=normalized,
                verified_at=utcnow() if verify_email else None,
                is_primary=True,
            )
        )
        session.add(
            UserProfile(
                user_id=user.id,
                display_name=clean_name,
                created_at=utcnow(),
            )
        )
        session.add(
            UserPassword(
                user_id=user.id,
                password_hash=passwords.hash(password),
                password_changed_at=utcnow(),
            )
        )
        session.flush()
    except IntegrityError as exc:
        raise AdminEmailConflict from exc

    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.create",
        resource_type="user",
        resource_id=user.id,
        reason=cleaned_reason,
        details={"email_verified_by_admin": verify_email},
    )
    return _view(session, user)


def change_email(
    session: Session,
    *,
    user_id: uuid.UUID,
    email: str,
    deliveries: EmailDeliveryService,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> tuple[str | None, str]:
    cleaned_reason = require_reason(reason)
    user = session.get(User, user_id)
    if user is None:
        raise AdminUserNotFound
    normalized = normalize_email(email)
    existing = _active_email(session, normalized)
    if existing is not None:
        if existing.user_id == user_id:
            raise AdminEmailUnchanged
        raise AdminEmailConflict

    old = _primary_email(session, user_id)
    old_email = old.email_normalized if old is not None else None
    if old is not None:
        old.released_at = utcnow()
        old.is_primary = False
        session.flush()
    session.add(
        UserEmail(
            user_id=user_id,
            email_normalized=normalized,
            verified_at=utcnow(),
            is_primary=True,
        )
    )
    session.flush()

    if old_email is not None:
        try:
            deliveries.enqueue(
                "email_change_notice",
                to=old_email,
                user_id=user_id,
                reference=f"admin-email:{uuid.uuid4()}",
                context={"occurred_at": utcnow().strftime("%d/%m/%Y %H:%M UTC")},
            )
        except EmailBudgetExhausted:
            pass

    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.email_change",
        resource_type="user",
        resource_id=user_id,
        reason=cleaned_reason,
        details={"old_email_present": old_email is not None, "sessions_revoked": True},
    )
    return old_email, normalized


def request_password_reset(
    session: Session,
    *,
    user_id: uuid.UUID,
    challenges: EmailChallengeService,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> None:
    cleaned_reason = require_reason(reason)
    user = session.get(User, user_id)
    if user is None:
        raise AdminUserNotFound
    credential = _primary_email(session, user_id)
    if credential is None:
        raise InvalidAdminUser
    challenges.request(
        credential.email_normalized,
        ChallengePurpose.password_reset,
        user_id=user_id,
    )
    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.password_reset",
        resource_type="user",
        resource_id=user_id,
        reason=cleaned_reason,
        details={},
    )


def suspend_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    until: datetime | None,
    sessions: SessionService,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> AdminUserView:
    cleaned_reason = require_reason(reason)
    user = session.get(User, user_id)
    if user is None:
        raise AdminUserNotFound
    user.status = "suspended"
    user.suspended_until = ensure_utc(until) if until is not None else None
    sessions.revoke_all(user_id, reason="admin_suspend")
    session.flush()
    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.suspend",
        resource_type="user",
        resource_id=user_id,
        reason=cleaned_reason,
        details={"until": user.suspended_until.isoformat() if user.suspended_until else None},
    )
    return _view(session, user)


def reactivate_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> AdminUserView:
    cleaned_reason = require_reason(reason)
    user = session.get(User, user_id)
    if user is None:
        raise AdminUserNotFound
    user.status = "active"
    user.suspended_until = None
    session.flush()
    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.reactivate",
        resource_type="user",
        resource_id=user_id,
        reason=cleaned_reason,
        details={},
    )
    return _view(session, user)


def revoke_sessions(
    session: Session,
    *,
    user_id: uuid.UUID,
    sessions: SessionService,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> int:
    cleaned_reason = require_reason(reason)
    if session.get(User, user_id) is None:
        raise AdminUserNotFound
    count = sessions.revoke_all(user_id, reason="admin_revoke")
    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="admin.user.sessions_revoke",
        resource_type="user",
        resource_id=user_id,
        reason=cleaned_reason,
        details={"revoked": count},
    )
    return count


def list_audit(session: Session, user_id: uuid.UUID) -> list[AuditLog]:
    if session.get(User, user_id) is None:
        raise AdminUserNotFound
    return list(
        session.scalars(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "user",
                AuditLog.resource_id == str(user_id),
            )
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    )


__all__ = [
    "AdminEmailConflict",
    "AdminEmailUnchanged",
    "AdminUserError",
    "AdminUserNotFound",
    "AdminUserView",
    "InvalidAdminUser",
    "ReasonRequired",
    "USER_STATUSES",
    "change_email",
    "create_user",
    "get_user",
    "list_audit",
    "reactivate_user",
    "request_password_reset",
    "require_reason",
    "revoke_sessions",
    "search_users",
    "suspend_user",
]
