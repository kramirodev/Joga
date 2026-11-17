"""Ciclo da assinatura do passe: criação, ativação e entrega mensal.

Regras (ADR 0042 §2, ADR 0043 §2):
- cobrança única por trimestre; a franquia cai mês a mês;
- a franquia não acumula e não é retroativa;
- cada entrega é idempotente por (assinatura, mês);
- o passe ativo libera a trilha paga enquanto estiver vigente.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.passes.models import PassDelivery, PassSubscription
from app.modules.passes.plans import PASS_MONTHS, get_plan
from app.modules.tickets.service import grant


class PassError(Exception):
    """Erro de assinatura do passe."""


class PassPlanNotFound(PassError):
    """Plano inexistente."""


class PassAlreadyActive(PassError):
    """Já existe assinatura vigente."""


class PassNotFound(PassError):
    """Assinatura inexistente ou de outro jogador."""


def add_months(moment: datetime, months: int) -> datetime:
    """Soma meses preservando fuso e ajustando o dia ao fim do mês."""

    index = moment.month - 1 + months
    year = moment.year + index // 12
    month = index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    plan_code: str,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Cria a intenção de assinatura. Ativação só acontece com pagamento."""

    moment = now or utcnow()
    plan = get_plan(plan_code)
    if plan is None:
        raise PassPlanNotFound

    active = active_subscription(session, user_id, moment)
    if active is not None:
        raise PassAlreadyActive

    pending = session.scalars(
        select(PassSubscription)
        .where(
            PassSubscription.user_id == user_id,
            PassSubscription.status == "pending",
        )
        .order_by(PassSubscription.created_at.desc())
    ).all()
    for item in pending:
        if item.plan_code == plan_code:
            return item
        item.status = "cancelled"

    subscription = PassSubscription(
        user_id=user_id,
        plan_code=plan.code,
        tickets_per_month=plan.tickets_per_month,
        amount_cents=plan.quarter_cents,
    )
    session.add(subscription)
    session.flush()
    return subscription


def get_subscription(
    session: Session, user_id: uuid.UUID, subscription_id: uuid.UUID
) -> PassSubscription:
    subscription = session.get(PassSubscription, subscription_id)
    if subscription is None or subscription.user_id != user_id:
        raise PassNotFound
    return subscription


def lock_subscription(session: Session, subscription_id: uuid.UUID) -> PassSubscription:
    subscription = session.scalars(
        select(PassSubscription).where(PassSubscription.id == subscription_id).with_for_update()
    ).first()
    if subscription is None:
        raise PassNotFound
    return subscription


def activate_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Marca a assinatura como paga e entrega o mês corrente. Idempotente."""

    moment = now or utcnow()
    subscription = lock_subscription(session, subscription_id)
    if subscription.status == "active":
        return subscription
    if subscription.status != "pending":
        raise PassError("subscription_not_pending")

    subscription.status = "active"
    subscription.starts_at = moment
    subscription.ends_at = add_months(moment, PASS_MONTHS)
    subscription.paid_at = moment
    from app.modules.ledger.flow import post_pass_sale

    post_pass_sale(session, subscription, now=moment)
    deliver_due(session, subscription, now=moment)
    session.flush()
    return subscription


def cancel_subscription(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
) -> PassSubscription:
    subscription = get_subscription(session, user_id, subscription_id)
    if subscription.status == "pending":
        subscription.status = "cancelled"
        session.flush()
    return subscription


def revoke_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Cancela uma assinatura reembolsada e impede entregas futuras."""

    subscription = lock_subscription(session, subscription_id)
    if subscription.status in {"cancelled", "expired"}:
        return subscription
    delivered = len(deliveries_for(session, subscription.id))
    refundable_months = max(0, PASS_MONTHS - delivered)
    subscription.status = "cancelled"
    subscription.ends_at = now or utcnow()
    from app.modules.ledger.flow import post_pass_refund

    post_pass_refund(
        session,
        subscription,
        amount_cents=(subscription.amount_cents // PASS_MONTHS) * refundable_months,
        now=now,
    )
    session.flush()
    return subscription


def active_subscription(
    session: Session,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> PassSubscription | None:
    moment = now or utcnow()
    subscriptions = session.scalars(
        select(PassSubscription).where(
            PassSubscription.user_id == user_id,
            PassSubscription.status == "active",
        )
    ).all()
    for subscription in subscriptions:
        if subscription.starts_at is None or subscription.ends_at is None:
            continue
        if ensure_utc(subscription.starts_at) <= moment < ensure_utc(subscription.ends_at):
            return subscription
    return None


def has_active_pass(
    session: Session,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    return active_subscription(session, user_id, now) is not None


def deliveries_for(session: Session, subscription_id: uuid.UUID) -> list[PassDelivery]:
    return list(
        session.scalars(
            select(PassDelivery)
            .where(PassDelivery.subscription_id == subscription_id)
            .order_by(PassDelivery.month_index.asc())
        ).all()
    )


def _month_index(subscription: PassSubscription, moment: datetime) -> int:
    if subscription.starts_at is None:
        return 0
    starts_at = ensure_utc(subscription.starts_at)
    if moment < starts_at:
        return 0
    elapsed = (moment.year - starts_at.year) * 12 + (moment.month - starts_at.month)
    return max(0, min(PASS_MONTHS, elapsed + 1))


def deliver_due(
    session: Session,
    subscription: PassSubscription,
    *,
    now: datetime | None = None,
) -> list[PassDelivery]:
    """Entrega as franquias mensais vencidas. Não paga mês anterior à compra."""

    if subscription.status != "active":
        return []
    moment = now or utcnow()
    target = _month_index(subscription, moment)
    if target <= 0 or subscription.starts_at is None:
        return []
    starts_at = ensure_utc(subscription.starts_at)

    existing = {item.month_index for item in deliveries_for(session, subscription.id)}
    created: list[PassDelivery] = []
    for month_index in range(1, target + 1):
        if month_index in existing:
            continue
        delivery = PassDelivery(
            subscription_id=subscription.id,
            month_index=month_index,
            tickets=subscription.tickets_per_month,
        )
        session.add(delivery)
        session.flush()
        grant(
            session,
            subscription.user_id,
            subscription.tickets_per_month,
            source="pass",
            idempotency_key=f"pass:{subscription.id}:{month_index}",
            ref_type="pass_delivery",
            ref_id=delivery.id,
            period=add_months(starts_at, month_index - 1).strftime("%Y-%m"),
        )
        from app.modules.ledger.flow import post_pass_month

        post_pass_month(
            session,
            subscription,
            month_index,
            amount_cents=subscription.amount_cents // PASS_MONTHS,
            now=moment,
        )
        created.append(delivery)
    return created


def deliver_all_due(session: Session, *, now: datetime | None = None) -> int:
    """Rotina diária: entrega meses vencidos e encerra assinaturas expiradas."""

    moment = now or utcnow()
    subscriptions = session.scalars(
        select(PassSubscription).where(PassSubscription.status == "active")
    ).all()
    delivered = 0
    for subscription in subscriptions:
        if subscription.starts_at is None:
            continue
        delivered += len(deliver_due(session, subscription, now=moment))
    expire_due(session, now=moment)
    return delivered


def expire_due(session: Session, *, now: datetime | None = None) -> int:
    moment = now or utcnow()
    expired = session.scalars(
        select(PassSubscription).where(PassSubscription.status == "active")
    ).all()
    count = 0
    for subscription in expired:
        if subscription.ends_at is None:
            continue
        if ensure_utc(subscription.ends_at) <= moment:
            subscription.status = "expired"
            count += 1
    return count


def next_delivery_at(
    subscription: PassSubscription, *, now: datetime | None = None
) -> datetime | None:
    """Data da próxima franquia ainda não entregue, se houver."""

    if subscription.status != "active" or subscription.starts_at is None:
        return None
    moment = now or utcnow()
    starts_at = ensure_utc(subscription.starts_at)
    delivered = _month_index(subscription, moment)
    if delivered >= PASS_MONTHS:
        return None
    return add_months(starts_at, delivered)
