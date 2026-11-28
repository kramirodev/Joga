"""Ciclo da assinatura: criação, ativação, entrega e expiração (ADR 0070).

Regras:
- contrato de 1, 3 ou 6 meses, cobrado uma vez por ciclo;
- preço e franquia congelados no contrato no momento da compra;
- a franquia cai mês a mês, no mês de aniversário da compra, e não acumula;
- cada ciclo tem ``starts_at``/``ends_at`` explícitos; o lote expira no fim dele;
- cada entrega é idempotente por (assinatura, mês);
- o passe ativo libera a trilha paga enquanto estiver vigente.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.passes.models import PassDelivery, PassSubscription
from app.modules.passes.plans import get_active_plan
from app.modules.tickets.models import TicketLot
from app.modules.tickets.service import grant


class PassError(Exception):
    """Erro de assinatura do passe."""


class PassPlanNotFound(PassError):
    """Plano inexistente ou inativo."""


class PassAlreadyActive(PassError):
    """Já existe assinatura vigente."""


class PassNotFound(PassError):
    """Assinatura inexistente ou de outro jogador."""


class ReceiptUnavailable(PassError):
    """Recibo só existe depois do pagamento confirmado."""


def add_months(moment: datetime, months: int) -> datetime:
    """Soma meses preservando fuso e ajustando o dia ao fim do mês."""

    index = moment.month - 1 + months
    year = moment.year + index // 12
    month = index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def cycle_amount_cents(subscription: PassSubscription, month_index: int) -> int:
    """Rateio do total do ciclo; o resto fica no último mês."""

    months = subscription.cycle_months
    monthly = subscription.amount_cents // months
    if month_index == months:
        return subscription.amount_cents - monthly * (months - 1)
    return monthly


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    plan_code: str,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Cria a intenção de assinatura com preço congelado. Ativação só com pagamento."""

    moment = now or utcnow()
    plan = get_active_plan(session, plan_code)
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
        item.cancelled_at = moment

    subscription = PassSubscription(
        user_id=user_id,
        plan_code=plan.code,
        tickets_per_month=plan.tickets_per_month,
        amount_cents=plan.cycle_amount_cents,
        cycle_months=plan.months,
        unit_price_cents=plan.unit_price_cents,
        installments=plan.installments,
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


def ensure_cycles(session: Session, subscription: PassSubscription) -> list[PassDelivery]:
    """Pré-cria os ciclos do contrato, um por mês, sempre idempotente."""

    existing = deliveries_for(session, subscription.id)
    if existing:
        return existing
    if subscription.starts_at is None:
        return []
    starts_at = ensure_utc(subscription.starts_at)
    cycles: list[PassDelivery] = []
    for month_index in range(1, subscription.cycle_months + 1):
        cycle_start = add_months(starts_at, month_index - 1)
        cycle_end = add_months(starts_at, month_index)
        cycle = PassDelivery(
            subscription_id=subscription.id,
            month_index=month_index,
            tickets=subscription.tickets_per_month,
            period=cycle_start.strftime("%Y-%m"),
            starts_at=cycle_start,
            ends_at=cycle_end,
            status="scheduled",
        )
        session.add(cycle)
        cycles.append(cycle)
    session.flush()
    return cycles


def activate_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Marca a assinatura como paga, cria os ciclos e entrega o mês corrente."""

    moment = now or utcnow()
    subscription = lock_subscription(session, subscription_id)
    if subscription.status in {"active", "scheduled"}:
        return subscription
    if subscription.status != "pending":
        raise PassError("subscription_not_pending")

    subscription.status = "active"
    subscription.starts_at = moment
    subscription.ends_at = add_months(moment, subscription.cycle_months)
    subscription.paid_at = moment
    subscription.refund_window_ends_at = moment + timedelta(days=7)
    from app.modules.ledger.flow import post_pass_sale

    post_pass_sale(session, subscription, now=moment)
    ensure_cycles(session, subscription)
    deliver_due(session, subscription, now=moment)
    session.flush()
    return subscription


def cancel_subscription(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    subscription = get_subscription(session, user_id, subscription_id)
    if subscription.status == "pending":
        subscription.status = "cancelled"
        subscription.cancelled_at = now or utcnow()
        for cycle in deliveries_for(session, subscription.id):
            if cycle.status == "scheduled":
                cycle.status = "cancelled"
        session.flush()
    return subscription


def revoke_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PassSubscription:
    """Cancela uma assinatura reembolsada e impede entregas futuras."""

    moment = now or utcnow()
    subscription = lock_subscription(session, subscription_id)
    if subscription.status in {"cancelled", "expired", "refunded"}:
        return subscription
    refundable = 0
    for cycle in deliveries_for(session, subscription.id):
        if cycle.status in {"scheduled", "cancelled"}:
            cycle.status = "cancelled"
            refundable += cycle_amount_cents(subscription, cycle.month_index)
    subscription.status = "cancelled"
    subscription.cancelled_at = moment
    subscription.ends_at = moment
    from app.modules.ledger.flow import post_pass_refund

    post_pass_refund(session, subscription, amount_cents=refundable, now=moment)
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


def current_delivery(
    subscription: PassSubscription,
    deliveries: list[PassDelivery],
    *,
    now: datetime | None = None,
) -> PassDelivery | None:
    moment = ensure_utc(now or utcnow())
    if subscription.status != "active":
        return None
    for cycle in deliveries:
        if cycle.status != "delivered":
            continue
        if ensure_utc(cycle.starts_at) <= moment < ensure_utc(cycle.ends_at):
            return cycle
    return None


def delivery_usage(
    session: Session, delivery: PassDelivery
) -> tuple[int, int, int, datetime | None]:
    """Uso do ciclo derivado do lote, sem contador editável."""

    lot = session.scalars(
        select(TicketLot).where(
            TicketLot.ref_type == "pass_delivery",
            TicketLot.ref_id == delivery.id,
        )
    ).first()
    if lot is None:
        return delivery.tickets, 0, delivery.tickets, ensure_utc(delivery.ends_at)
    used = lot.original_amount - lot.remaining
    return lot.original_amount, used, lot.remaining, lot.expires_at


def deliver_due(
    session: Session,
    subscription: PassSubscription,
    *,
    now: datetime | None = None,
) -> list[PassDelivery]:
    """Entrega apenas o ciclo corrente. Mês operacionalmente perdido não é retroativo."""

    if subscription.status != "active":
        return []
    moment = ensure_utc(now or utcnow())
    cycles = ensure_cycles(session, subscription)
    created: list[PassDelivery] = []
    for cycle in cycles:
        if cycle.status != "scheduled":
            continue
        cycle_start = ensure_utc(cycle.starts_at)
        cycle_end = ensure_utc(cycle.ends_at)
        if moment < cycle_start or moment >= cycle_end:
            continue
        grant(
            session,
            subscription.user_id,
            cycle.tickets,
            source="pass",
            idempotency_key=f"pass:{subscription.id}:{cycle.month_index}",
            ref_type="pass_delivery",
            ref_id=cycle.id,
            period=cycle.period,
            expires_at=cycle_end,
        )
        from app.modules.ledger.flow import post_pass_month

        post_pass_month(
            session,
            subscription,
            cycle.month_index,
            amount_cents=cycle_amount_cents(subscription, cycle.month_index),
            now=moment,
        )
        cycle.status = "delivered"
        cycle.delivered_at = moment
        created.append(cycle)
    return created


def deliver_all_due(session: Session, *, now: datetime | None = None) -> int:
    """Rotina periódica: entrega ciclos correntes e encerra contratos vencidos."""

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
    """Fecha ciclos vencidos e encerra contratos. Idempotente."""

    moment = ensure_utc(now or utcnow())
    cycles = session.scalars(
        select(PassDelivery).where(
            PassDelivery.status.in_(("scheduled", "delivered")),
            PassDelivery.ends_at <= moment,
        )
    ).all()
    for cycle in cycles:
        cycle.closed_at = moment
        cycle.status = "closed" if cycle.status == "delivered" else "cancelled"

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
    session.flush()
    return count


def next_delivery_at(
    session: Session,
    subscription: PassSubscription,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Data do próximo ciclo ainda não entregue, se houver."""

    if subscription.status != "active" or subscription.starts_at is None:
        return None
    moment = ensure_utc(now or utcnow())
    for cycle in deliveries_for(session, subscription.id):
        if cycle.status != "scheduled":
            continue
        if ensure_utc(cycle.starts_at) > moment:
            return ensure_utc(cycle.starts_at)
    return None
