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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.clans.models import (
    Clan,
    ClanJoinRequest,
    ClanMember,
    ClanMessage,
    ClanReport,
    ClanTrophyEvent,
    ClanTrophySnapshot,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import ensure_utc, utcnow

MAX_MEMBERS = 30
JOIN_COOLDOWN = timedelta(days=7)
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
