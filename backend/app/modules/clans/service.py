"""Regras de clã: entrada por aprovação, papéis, chat e troféus (Fase 16).

Decisões aprovadas:
- até 30 membros;
- entrada por aprovação (política padrão), com "aberto" e "fechado" disponíveis;
- troca de clã livre, com carência de 7 dias;
- troféus por temporada e formato;
- denúncia oculta a mensagem imediatamente.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.clans.models import (
    JOIN_POLICIES,
    Clan,
    ClanInvite,
    ClanJoinRequest,
    ClanMember,
    ClanMessage,
    ClanReport,
    ClanTrophyEvent,
    ClanTrophySnapshot,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User
from app.modules.notifications.service import NotificationService
from app.modules.social.service import SocialService

MAX_MEMBERS = 30
JOIN_COOLDOWN = timedelta(days=7)
INVITE_TTL = timedelta(days=7)
TROPHY_MIN_TENURE = timedelta(days=7)
TROPHY_MEMBERS_COUNTED = 10
TROPHY_POINTS = {"WIN": 50, "DRAW": 30, "LOSS": 20}
CLAN_TAG_CORE_PATTERN = re.compile(r"[A-Z0-9]{2,7}")


def normalize_clan_tag(tag: str) -> str:
    """Canonicaliza a tag como ``#MIOLO`` (miolo A-Z/0-9, 2 a 7 caracteres).

    Aceita ``6666``, ``#6666`` e espaços nas bordas. O cliente pode exibir só o
    miolo, mas a API e o banco guardam sempre a forma canônica com ``#``.
    """

    core = tag.strip().lstrip("#").strip().upper()
    if CLAN_TAG_CORE_PATTERN.fullmatch(core) is None:
        raise ClanConflict("tag_invalid")
    return f"#{core}"


class ClanError(Exception):
    """Erro de clã."""


class ClanNotFound(ClanError):
    """Clã, pedido, mensagem ou denúncia inexistente."""


class ClanConflict(ClanError):
    """Regra de entrada, nome ou estado violada."""


class ClanForbidden(ClanError):
    """Ação não permitida para o papel do jogador."""


class ClanValidation(ClanError):
    """Valor de campo inválido em uma edição (responde 422)."""


class ClanFull(ClanError):
    """Clã sem vaga."""


class ClanCooldown(ClanError):
    """Carência de troca de clã ainda vigente."""


def get_clan(session: Session, clan_id: uuid.UUID) -> Clan:
    clan = session.get(Clan, clan_id)
    if clan is None or clan.status != "active":
        raise ClanNotFound
    return clan


def active_membership(session: Session, user_id: uuid.UUID) -> ClanMember | None:
    return session.scalars(
        select(ClanMember).where(
            ClanMember.user_id == user_id,
            ClanMember.status == "active",
        )
    ).first()


def active_clan_for(session: Session, user_id: uuid.UUID) -> Clan | None:
    membership = active_membership(session, user_id)
    if membership is None:
        return None
    return session.get(Clan, membership.clan_id)


def member_count(session: Session, clan_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ClanMember)
            .where(
                ClanMember.clan_id == clan_id,
                ClanMember.status == "active",
            )
        )
        or 0
    )


def membership_of(session: Session, clan_id: uuid.UUID, user_id: uuid.UUID) -> ClanMember | None:
    membership = session.get(ClanMember, (clan_id, user_id))
    if membership is None or membership.status != "active":
        return None
    return membership


def require_member(
    session: Session,
    clan_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ClanMember:
    if for_update:
        membership = session.scalars(
            select(ClanMember)
            .where(
                ClanMember.clan_id == clan_id,
                ClanMember.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if membership is not None and membership.status != "active":
            membership = None
    else:
        membership = membership_of(session, clan_id, user_id)
    if membership is None:
        raise ClanForbidden("not_a_member")
    return membership


def require_admin(
    session: Session,
    clan_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ClanMember:
    membership = require_member(session, clan_id, user_id, for_update=for_update)
    if membership.role not in ("owner", "admin"):
        raise ClanForbidden("admin_required")
    return membership


def require_owner(
    session: Session,
    clan_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ClanMember:
    membership = require_member(session, clan_id, user_id, for_update=for_update)
    if membership.role != "owner":
        raise ClanForbidden("owner_required")
    return membership


def cooldown_until(session: Session, user_id: uuid.UUID) -> datetime | None:
    last_left = session.scalar(
        select(func.max(ClanMember.left_at)).where(
            ClanMember.user_id == user_id,
            ClanMember.status.in_(("left", "removed")),
        )
    )
    if last_left is None:
        return None
    return ensure_utc(last_left) + JOIN_COOLDOWN


def _check_cooldown(session: Session, user_id: uuid.UUID, moment: datetime) -> None:
    until = cooldown_until(session, user_id)
    if until is not None and moment < until:
        raise ClanCooldown


def create_clan(
    session: Session,
    user_id: uuid.UUID,
    *,
    name: str,
    tag: str,
    description: str | None = None,
    now: datetime | None = None,
) -> Clan:
    moment = now or utcnow()
    if active_membership(session, user_id) is not None:
        raise ClanConflict("already_in_clan")
    clean_name = name.strip()
    if not 3 <= len(clean_name) <= 40:
        raise ClanConflict("name_invalid")
    clean_tag = normalize_clan_tag(tag)
    if session.scalars(select(Clan.id).where(Clan.name == clean_name)).first() is not None:
        raise ClanConflict("name_taken")
    if session.scalars(select(Clan.id).where(Clan.tag == clean_tag)).first() is not None:
        raise ClanConflict("tag_taken")

    clan = Clan(
        name=clean_name,
        tag=clean_tag,
        description=description.strip() if description else None,
        created_by=user_id,
        join_policy="approval",
    )
    session.add(clan)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ClanConflict("name_or_tag_taken") from exc
    session.add(
        ClanMember(
            clan_id=clan.id,
            user_id=user_id,
            role="owner",
            status="active",
            joined_at=moment,
        )
    )
    session.flush()
    return clan


def update_clan(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    *,
    changes: dict[str, str | None],
) -> Clan:
    """Edita nome, descrição e política de entrada; a tag nunca muda.

    ``changes`` contém somente os campos enviados pelo cliente. Cada alteração
    efetiva é registrada em auditoria como ``clan.updated``. Campos ausentes ou
    iguais ao valor atual não geram evento.
    """

    clan = get_clan(session, clan_id)
    require_admin(session, clan_id, actor_id)
    applied: dict[str, dict[str, str | None]] = {}

    if "name" in changes:
        clean_name = (changes["name"] or "").strip()
        if not 3 <= len(clean_name) <= 40:
            raise ClanValidation("name_invalid")
        if clean_name != clan.name:
            taken = session.scalars(
                select(Clan.id).where(Clan.name == clean_name, Clan.id != clan.id)
            ).first()
            if taken is not None:
                raise ClanConflict("name_taken")
            applied["name"] = {"from": clan.name, "to": clean_name}
            clan.name = clean_name

    if "description" in changes:
        raw_description = changes["description"]
        clean_description = raw_description.strip() if raw_description else None
        if clean_description is not None and len(clean_description) > 280:
            raise ClanValidation("description_invalid")
        if clean_description != clan.description:
            applied["description"] = {"from": clan.description, "to": clean_description}
            clan.description = clean_description

    if "join_policy" in changes:
        policy = changes["join_policy"]
        if policy not in JOIN_POLICIES:
            raise ClanValidation("join_policy_invalid")
        if policy != clan.join_policy:
            applied["join_policy"] = {"from": clan.join_policy, "to": policy}
            clan.join_policy = policy

    if applied:
        try:
            session.flush()
        except IntegrityError as exc:
            raise ClanConflict("name_taken") from exc
        record_audit(
            session,
            actor_user_id=actor_id,
            action="clan.updated",
            resource_type="clan",
            resource_id=clan.id,
            details={"changes": applied},
        )
        session.flush()
    return clan


def request_join(
    session: Session,
    user_id: uuid.UUID,
    clan_id: uuid.UUID,
    *,
    message: str | None = None,
    now: datetime | None = None,
) -> ClanJoinRequest | None:
    moment = now or utcnow()
    clan = get_clan(session, clan_id)
    # Quem já é membro ativo recebe o código específico, mesmo em clã fechado.
    if membership_of(session, clan.id, user_id) is not None:
        raise ClanConflict("already_member")
    if clan.join_policy == "closed":
        raise ClanConflict("clan_closed")
    if active_membership(session, user_id) is not None:
        raise ClanConflict("already_in_clan")
    _check_cooldown(session, user_id, moment)

    if clan.join_policy == "open":
        _add_member(session, clan, user_id, moment)
        return None

    existing = session.scalars(
        select(ClanJoinRequest).where(
            ClanJoinRequest.clan_id == clan.id,
            ClanJoinRequest.user_id == user_id,
            ClanJoinRequest.status == "pending",
        )
    ).first()
    if existing is not None:
        return existing
    request = ClanJoinRequest(
        clan_id=clan.id,
        user_id=user_id,
        message=message.strip()[:200] if message else None,
        status="pending",
    )
    session.add(request)
    session.flush()
    return request


def _add_member(
    session: Session,
    clan: Clan,
    user_id: uuid.UUID,
    moment: datetime,
) -> ClanMember:
    if member_count(session, clan.id) >= MAX_MEMBERS:
        raise ClanFull
    _check_cooldown(session, user_id, moment)
    membership = session.get(ClanMember, (clan.id, user_id))
    if membership is None:
        membership = ClanMember(
            clan_id=clan.id,
            user_id=user_id,
            role="member",
            status="active",
            joined_at=moment,
        )
        session.add(membership)
    else:
        membership.role = "member"
        membership.status = "active"
        membership.joined_at = moment
        membership.left_at = None
    session.flush()
    pending = session.scalars(
        select(ClanJoinRequest).where(
            ClanJoinRequest.user_id == user_id,
            ClanJoinRequest.status == "pending",
        )
    ).all()
    for item in pending:
        item.status = "cancelled"
    return membership


def decide_request(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    request_id: uuid.UUID,
    *,
    approve: bool,
    note: str | None = None,
    now: datetime | None = None,
) -> ClanJoinRequest:
    moment = now or utcnow()
    _clan = get_clan(session, clan_id)
    require_admin(session, clan_id, actor_id)
    request = session.scalars(
        select(ClanJoinRequest)
        .where(
            ClanJoinRequest.id == request_id,
            ClanJoinRequest.clan_id == clan_id,
        )
        .with_for_update()
    ).first()
    if request is None:
        raise ClanNotFound
    if request.status != "pending":
        return request

    if approve:
        if active_membership(session, request.user_id) is not None:
            raise ClanConflict("already_in_clan")
        _add_member(session, _clan, request.user_id, moment)
        request.status = "approved"
    else:
        request.status = "rejected"
    request.decided_by = actor_id
    request.decided_at = moment
    if note:
        request.message = request.message or note.strip()[:200]
    session.flush()
    return request


def leave_clan(
    session: Session,
    user_id: uuid.UUID,
    clan_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanMember:
    moment = now or utcnow()
    membership = require_member(session, clan_id, user_id)
    if membership.role == "owner":
        raise ClanConflict("transfer_ownership_first")
    membership.status = "left"
    membership.left_at = moment
    session.flush()
    return membership


def invite_to_clan(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    invitee_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanInvite:
    """Convida um amigo aceito e não bloqueado para o clã.

    Qualquer clã pendente do convidado em outro clã não impede o convite: a
    exclusividade de clã ativo é verificada no aceite. A notificação ao
    convidado usa a central existente (e a Outbox), sem criar evento novo.
    """

    moment = ensure_utc(now or utcnow())
    clan = get_clan(session, clan_id)
    require_admin(session, clan_id, actor_id)
    if actor_id == invitee_id:
        raise ClanConflict("cannot_invite_self")
    if session.get(User, invitee_id) is None:
        raise ClanNotFound

    social = SocialService(session)
    if social.is_blocked(actor_id, invitee_id):
        raise ClanForbidden("blocked")
    if not social.are_friends(actor_id, invitee_id):
        raise ClanForbidden("not_friends")
    if membership_of(session, clan.id, invitee_id) is not None:
        raise ClanConflict("already_member")
    if member_count(session, clan.id) >= MAX_MEMBERS:
        raise ClanFull

    session.execute(
        update(ClanInvite)
        .where(
            ClanInvite.clan_id == clan.id,
            ClanInvite.invitee_id == invitee_id,
            ClanInvite.status == "pending",
            ClanInvite.expires_at <= moment,
        )
        .values(status="expired", answered_at=moment)
    )
    existing = session.scalars(
        select(ClanInvite.id).where(
            ClanInvite.clan_id == clan.id,
            ClanInvite.invitee_id == invitee_id,
            ClanInvite.status == "pending",
        )
    ).first()
    if existing is not None:
        raise ClanConflict("already_invited")

    invite = ClanInvite(
        clan_id=clan.id,
        inviter_id=actor_id,
        invitee_id=invitee_id,
        status="pending",
        created_at=moment,
        expires_at=moment + INVITE_TTL,
    )
    session.add(invite)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ClanConflict("already_invited") from exc

    NotificationService(session).create(
        user_id=invitee_id,
        kind="clan_invite",
        title="Convite de clã",
        body=f"{clan.name} te convidou para entrar no clã.",
        idempotency_key=f"clan_invite:{invite.id}",
        data={
            "invite_id": str(invite.id),
            "clan_id": str(clan.id),
            "clan_name": clan.name,
            "clan_tag": clan.tag,
            "inviter_id": str(actor_id),
        },
        now=moment,
    )
    return invite


def list_pending_invites(
    session: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> list[ClanInvite]:
    """Convites ainda válidos do próprio jogador, mais recentes primeiro."""

    moment = ensure_utc(now or utcnow())
    session.execute(
        update(ClanInvite)
        .where(
            ClanInvite.invitee_id == user_id,
            ClanInvite.status == "pending",
            ClanInvite.expires_at <= moment,
        )
        .values(status="expired", answered_at=moment)
    )
    return list(
        session.scalars(
            select(ClanInvite)
            .where(
                ClanInvite.invitee_id == user_id,
                ClanInvite.status == "pending",
                ClanInvite.expires_at > moment,
            )
            .order_by(ClanInvite.created_at.desc(), ClanInvite.id)
        )
    )


def _invite_for(
    session: Session,
    invite_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ClanInvite:
    statement = select(ClanInvite).where(ClanInvite.id == invite_id)
    if for_update:
        statement = statement.with_for_update()
    invite = session.scalars(statement).first()
    if invite is None:
        raise ClanNotFound
    return invite


def _expire(invite: ClanInvite, moment: datetime) -> None:
    invite.status = "expired"
    invite.answered_at = moment


def accept_invite(
    session: Session,
    user_id: uuid.UUID,
    invite_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanInvite:
    """Aceita o convite do próprio jogador e o torna membro ativo.

    Exige convite pendente e não expirado, ausência de clã ativo e vaga no clã.
    A carência de troca de clã é a mesma de ``request_join``. A ação é auditada.
    """

    moment = ensure_utc(now or utcnow())
    invite = _invite_for(session, invite_id, for_update=True)
    if invite.invitee_id != user_id:
        raise ClanNotFound
    if invite.status == "expired":
        raise ClanConflict("invite_expired")
    if invite.status != "pending":
        raise ClanConflict("invite_not_pending")
    if ensure_utc(invite.expires_at) <= moment:
        # O status ``expired`` é materializado pela listagem/próximo convite;
        # aqui só recusamos, sem gravar no meio de uma requisição que falha.
        raise ClanConflict("invite_expired")

    clan = get_clan(session, invite.clan_id)
    if active_membership(session, user_id) is not None:
        raise ClanConflict("already_in_clan")
    _add_member(session, clan, user_id, moment)
    invite.status = "accepted"
    invite.answered_at = moment
    record_audit(
        session,
        actor_user_id=user_id,
        action="clan.invite_accepted",
        resource_type="clan",
        resource_id=clan.id,
        details={
            "invite_id": str(invite.id),
            "inviter_id": str(invite.inviter_id),
            "invitee_id": str(user_id),
        },
    )
    session.flush()
    return invite


def decline_invite(
    session: Session,
    user_id: uuid.UUID,
    invite_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanInvite:
    """Recusa o convite do próprio jogador. Convite expirado não é recusado."""

    moment = ensure_utc(now or utcnow())
    invite = _invite_for(session, invite_id, for_update=True)
    if invite.invitee_id != user_id:
        raise ClanNotFound
    if invite.status == "expired":
        raise ClanConflict("invite_expired")
    if invite.status != "pending":
        raise ClanConflict("invite_not_pending")
    if ensure_utc(invite.expires_at) <= moment:
        raise ClanConflict("invite_expired")
    invite.status = "declined"
    invite.answered_at = moment
    session.flush()
    return invite


def cancel_invite(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    invite_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanInvite:
    """Cancela um convite pendente do clã.

    O status fechado do modelo não tem ``cancelled``; o cancelamento usa
    ``expired`` com ``answered_at`` preenchido, e a auditoria guarda o motivo
    (``cancelled_by_admin``). Assim o histórico não some e o índice único
    parcial libera novo convite.
    """

    moment = ensure_utc(now or utcnow())
    require_admin(session, clan_id, actor_id)
    invite = _invite_for(session, invite_id, for_update=True)
    if invite.clan_id != clan_id:
        raise ClanNotFound
    if invite.status != "pending":
        raise ClanConflict("invite_not_pending")
    _expire(invite, moment)
    record_audit(
        session,
        actor_user_id=actor_id,
        action="clan.invite_cancelled",
        resource_type="clan",
        resource_id=clan_id,
        details={
            "invite_id": str(invite.id),
            "invitee_id": str(invite.invitee_id),
            "reason": "cancelled_by_admin",
        },
    )
    session.flush()
    return invite


def remove_member(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    target_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> ClanMember:
    moment = now or utcnow()
    actor = require_admin(session, clan_id, actor_id)
    if actor_id == target_id:
        raise ClanConflict("use_leave")
    target = session.get(ClanMember, (clan_id, target_id))
    if target is None or target.status != "active":
        raise ClanNotFound
    if target.role == "owner":
        raise ClanForbidden("cannot_remove_owner")
    if target.role == "admin" and actor.role != "owner":
        raise ClanForbidden("owner_required")
    target.status = "removed"
    target.left_at = moment
    session.flush()
    return target


def set_role(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    target_id: uuid.UUID,
    *,
    role: str,
) -> ClanMember:
    require_owner(session, clan_id, actor_id)
    if role not in ("admin", "member"):
        raise ClanConflict("role_invalid")
    target = session.get(ClanMember, (clan_id, target_id))
    if target is None or target.status != "active":
        raise ClanNotFound
    if target.role == "owner":
        raise ClanForbidden("use_transfer")
    target.role = role
    session.flush()
    return target


def transfer_ownership(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    target_id: uuid.UUID,
) -> ClanMember:
    """Transfere a posse em uma transação, rebaixando o antigo dono a membro.

    O ``FOR UPDATE`` no autor serializa transferências concorrentes do mesmo
    clã; o alvo também é travado antes de trocar os papéis.
    """

    actor = require_owner(session, clan_id, actor_id, for_update=True)
    if actor_id == target_id:
        raise ClanConflict("already_owner")
    target = session.scalars(
        select(ClanMember)
        .where(
            ClanMember.clan_id == clan_id,
            ClanMember.user_id == target_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if target is None or target.status != "active":
        raise ClanNotFound
    actor.role = "member"
    target.role = "owner"
    record_audit(
        session,
        actor_user_id=actor_id,
        action="clan.ownership_transferred",
        resource_type="clan",
        resource_id=clan_id,
        details={"from_user_id": str(actor_id), "to_user_id": str(target_id)},
    )
    session.flush()
    return target


def send_message(
    session: Session,
    user_id: uuid.UUID,
    clan_id: uuid.UUID,
    body: str,
    *,
    now: datetime | None = None,
) -> ClanMessage:
    require_member(session, clan_id, user_id)
    clean = body.strip()
    if not 1 <= len(clean) <= 2000:
        raise ClanConflict("body_invalid")
    message = ClanMessage(
        clan_id=clan_id,
        sender_id=user_id,
        body=clean,
        created_at=now or utcnow(),
    )
    session.add(message)
    session.flush()
    return message


def list_messages(
    session: Session,
    user_id: uuid.UUID,
    clan_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[ClanMessage]:
    membership = require_member(session, clan_id, user_id)
    statement = select(ClanMessage).where(ClanMessage.clan_id == clan_id)
    if membership.role == "member":
        statement = statement.where(ClanMessage.hidden_at.is_(None))
    statement = statement.order_by(ClanMessage.created_at.desc()).limit(max(1, min(limit, 100)))
    return list(session.scalars(statement))


def report_message(
    session: Session,
    user_id: uuid.UUID,
    clan_id: uuid.UUID,
    message_id: uuid.UUID,
    reason: str,
    *,
    now: datetime | None = None,
) -> ClanReport:
    moment = now or utcnow()
    require_member(session, clan_id, user_id)
    message = session.get(ClanMessage, message_id)
    if message is None or message.clan_id != clan_id:
        raise ClanNotFound
    if not 1 <= len(reason.strip()) <= 300:
        raise ClanConflict("reason_invalid")
    existing = session.scalars(
        select(ClanReport).where(
            ClanReport.message_id == message_id,
            ClanReport.reporter_id == user_id,
        )
    ).first()
    if existing is not None:
        return existing
    message.hidden_at = moment
    message.hidden_by = user_id
    report = ClanReport(
        clan_id=clan_id,
        message_id=message_id,
        reporter_id=user_id,
        reason=reason.strip(),
        status="OPEN",
        created_at=moment,
    )
    session.add(report)
    session.flush()
    return report


def list_reports(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    *,
    status_filter: str | None = None,
) -> list[ClanReport]:
    require_admin(session, clan_id, actor_id)
    statement = select(ClanReport).where(ClanReport.clan_id == clan_id)
    if status_filter is not None:
        statement = statement.where(ClanReport.status == status_filter)
    return list(session.scalars(statement.order_by(ClanReport.created_at.desc())))


def decide_report(
    session: Session,
    actor_id: uuid.UUID,
    clan_id: uuid.UUID,
    report_id: uuid.UUID,
    *,
    decision: str,
    note: str | None = None,
    now: datetime | None = None,
) -> ClanReport:
    moment = now or utcnow()
    require_admin(session, clan_id, actor_id)
    if decision not in ("KEEP_HIDDEN", "RESTORE"):
        raise ClanConflict("decision_invalid")
    report = session.get(ClanReport, report_id)
    if report is None or report.clan_id != clan_id:
        raise ClanNotFound
    if report.status != "OPEN":
        return report
    message = session.get(ClanMessage, report.message_id)
    if message is not None:
        if decision == "RESTORE":
            message.hidden_at = None
            message.hidden_by = None
        else:
            message.hidden_at = message.hidden_at or moment
    report.status = "KEEP_HIDDEN" if decision == "KEEP_HIDDEN" else "RESTORED"
    report.reviewed_by = actor_id
    report.reviewed_at = moment
    report.decision_note = note.strip()[:300] if note else None
    session.flush()
    return report


def clans_for_users(session: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, ClanMember]:
    if not user_ids:
        return {}
    rows = session.scalars(
        select(ClanMember).where(
            ClanMember.user_id.in_(user_ids),
            ClanMember.status == "active",
        )
    )
    return {member.user_id: member for member in rows}


def record_match_trophies(
    session: Session,
    *,
    match_id: uuid.UUID,
    format_id: uuid.UUID,
    season_id: uuid.UUID | None,
    results: dict[uuid.UUID, str],
    now: datetime | None = None,
) -> int:
    """Credita troféus por partida. Repetição não duplica."""
    if not results:
        return 0
    moment = now or utcnow()
    memberships = clans_for_users(session, list(results.keys()))
    applied = 0
    for user_id, result in results.items():
        membership = memberships.get(user_id)
        if membership is None:
            continue
        if ensure_utc(membership.joined_at) > moment - TROPHY_MIN_TENURE:
            continue
        already = session.scalars(
            select(ClanTrophyEvent.id).where(
                ClanTrophyEvent.match_id == match_id,
                ClanTrophyEvent.user_id == user_id,
            )
        ).first()
        if already is not None:
            continue
        session.add(
            ClanTrophyEvent(
                clan_id=membership.clan_id,
                user_id=user_id,
                match_id=match_id,
                format_id=format_id,
                season_id=season_id,
                result=result,
                points=TROPHY_POINTS.get(result, 0),
                created_at=moment,
            )
        )
        applied += 1
    session.flush()
    return applied


def _counted_member_points(
    session: Session,
    *,
    clan_id: uuid.UUID,
    season_id: uuid.UUID | None = None,
    format_id: uuid.UUID | None = None,
) -> int:
    """Soma os 10 melhores membros: volume não vira troféu infinito."""

    statement = (
        select(
            ClanTrophyEvent.user_id,
            func.coalesce(func.sum(ClanTrophyEvent.points), 0),
        )
        .where(ClanTrophyEvent.clan_id == clan_id)
        .group_by(ClanTrophyEvent.user_id)
    )
    if season_id is not None:
        statement = statement.where(ClanTrophyEvent.season_id == season_id)
    if format_id is not None:
        statement = statement.where(ClanTrophyEvent.format_id == format_id)
    totals = sorted((int(total or 0) for _user, total in session.execute(statement)), reverse=True)
    return sum(totals[:TROPHY_MEMBERS_COUNTED])


def trophy_total(
    session: Session,
    clan_id: uuid.UUID,
    *,
    season_id: uuid.UUID | None = None,
    format_id: uuid.UUID | None = None,
) -> int:
    return _counted_member_points(
        session,
        clan_id=clan_id,
        season_id=season_id,
        format_id=format_id,
    )


def clan_ranking(
    session: Session,
    *,
    season_id: uuid.UUID | None = None,
    format_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[tuple[Clan, int]]:
    statement = select(
        ClanTrophyEvent.clan_id,
        ClanTrophyEvent.user_id,
        func.coalesce(func.sum(ClanTrophyEvent.points), 0),
    ).group_by(ClanTrophyEvent.clan_id, ClanTrophyEvent.user_id)
    if season_id is not None:
        statement = statement.where(ClanTrophyEvent.season_id == season_id)
    if format_id is not None:
        statement = statement.where(ClanTrophyEvent.format_id == format_id)

    per_clan: dict[uuid.UUID, list[int]] = {}
    for clan_id, _user_id, total in session.execute(statement):
        per_clan.setdefault(clan_id, []).append(int(total or 0))
    totals = {
        clan_id: sum(sorted(points, reverse=True)[:TROPHY_MEMBERS_COUNTED])
        for clan_id, points in per_clan.items()
    }
    if not totals:
        return []
    clans = session.scalars(
        select(Clan).where(
            Clan.id.in_(list(totals.keys())),
            Clan.status == "active",
        )
    ).all()
    ordered = sorted(
        ((clan, totals[clan.id]) for clan in clans),
        key=lambda item: (-item[1], item[0].name),
    )
    return ordered[: max(1, min(limit, 100))]


def snapshot_season(session: Session, season_id: uuid.UUID) -> int:
    """Grava o fechamento dos troféus por clã e formato. Idempotente."""

    rows = session.execute(
        select(
            ClanTrophyEvent.clan_id,
            ClanTrophyEvent.format_id,
            ClanTrophyEvent.user_id,
            func.coalesce(func.sum(ClanTrophyEvent.points), 0),
        )
        .where(ClanTrophyEvent.season_id == season_id)
        .group_by(
            ClanTrophyEvent.clan_id,
            ClanTrophyEvent.format_id,
            ClanTrophyEvent.user_id,
        )
    )
    grouped: dict[tuple[uuid.UUID, uuid.UUID], list[int]] = {}
    for clan_id, format_id, _user_id, total in rows:
        grouped.setdefault((clan_id, format_id), []).append(int(total or 0))

    created = 0
    for (clan_id, format_id), points in grouped.items():
        total = sum(sorted(points, reverse=True)[:TROPHY_MEMBERS_COUNTED])
        existing = session.scalars(
            select(ClanTrophySnapshot.id).where(
                ClanTrophySnapshot.clan_id == clan_id,
                ClanTrophySnapshot.season_id == season_id,
                ClanTrophySnapshot.format_id == format_id,
            )
        ).first()
        if existing is not None:
            continue
        session.add(
            ClanTrophySnapshot(
                clan_id=clan_id,
                season_id=season_id,
                format_id=format_id,
                points=total,
            )
        )
        created += 1
    session.flush()
    return created
