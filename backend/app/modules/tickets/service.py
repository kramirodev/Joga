"""Operações da carteira de ingressos (ADR 0042 §2).

Regras:
- todo movimento é evento no ledger append-only, com chave de idempotência;
- o saldo é projeção e nunca pode ficar negativo;
- consumo exige saldo; devolução é evento positivo.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.tickets.models import (
    TicketBalance,
    TicketLedgerEntry,
    TicketPack,
    TicketPurchase,
)


class TicketError(Exception):
    """Erro de carteira de ingressos."""


class InsufficientTickets(TicketError):
    """Saldo insuficiente para a operação."""


class TicketConflict(TicketError):
    """Chave de idempotência reutilizada com efeito diferente."""


class PackNotFound(TicketError):
    """Pacote inexistente ou inativo."""


class PurchaseNotFound(TicketError):
    """Compra inexistente ou de outro jogador."""


DEFAULT_PACKS: tuple[tuple[str, str, int, int], ...] = (
    ("avulso", "Avulso", 3, 370),
    ("pequeno", "Pequeno", 10, 340),
    ("medio", "Médio", 30, 320),
    ("grande", "Grande", 50, 310),
)


def seed_default_packs(session: Session) -> None:
    """Garante os pacotes da escada de preço. Idempotente."""

    existing = set(session.scalars(select(TicketPack.code)).all())
    for code, label, tickets, unit_price_cents in DEFAULT_PACKS:
        if code in existing:
            continue
        session.add(
            TicketPack(
                code=code,
                label=label,
                tickets=tickets,
                unit_price_cents=unit_price_cents,
            )
        )
    session.flush()


def list_packs(session: Session) -> Sequence[TicketPack]:
    return session.scalars(
        select(TicketPack)
        .where(TicketPack.active.is_(True))
        .order_by(TicketPack.tickets.asc())
    ).all()


def get_pack(session: Session, code: str) -> TicketPack:
    pack = session.scalars(
        select(TicketPack).where(TicketPack.code == code, TicketPack.active.is_(True))
    ).first()
    if pack is None:
        raise PackNotFound
    return pack


def create_purchase(session: Session, user_id: uuid.UUID, pack_code: str) -> TicketPurchase:
    """Registra a intenção de compra. A cobrança real entra na Fase 14B."""

    pack = get_pack(session, pack_code)
    purchase = TicketPurchase(
        user_id=user_id,
        pack_id=pack.id,
        tickets=pack.tickets,
        amount_cents=pack.amount_cents,
    )
    session.add(purchase)
    session.flush()
    return purchase


def confirm_purchase(
    session: Session, user_id: uuid.UUID, purchase_id: uuid.UUID
) -> tuple[TicketPurchase, int]:
    """Marca a compra como paga e credita os ingressos, sem duplicar."""

    purchase = session.get(TicketPurchase, purchase_id)
    if purchase is None or purchase.user_id != user_id:
        raise PurchaseNotFound
    if purchase.status == "paid":
        return purchase, get_balance(session, user_id)
    purchase.status = "paid"
    purchase.paid_at = purchase.paid_at or utcnow()
    balance = grant(
        session,
        user_id,
        purchase.tickets,
        source="purchase",
        idempotency_key=f"purchase:{purchase.id}",
        ref_type="purchase",
        ref_id=purchase.id,
    )
    return purchase, balance


def get_balance(session: Session, user_id: uuid.UUID) -> int:
    record = session.get(TicketBalance, user_id)
    return record.balance if record is not None else 0


def list_entries(
    session: Session, user_id: uuid.UUID, *, limit: int = 20
) -> Sequence[TicketLedgerEntry]:
    return session.scalars(
        select(TicketLedgerEntry)
        .where(TicketLedgerEntry.user_id == user_id)
        .order_by(TicketLedgerEntry.created_at.desc(), TicketLedgerEntry.id.desc())
        .limit(limit)
    ).all()


def _lock_balance(session: Session, user_id: uuid.UUID) -> TicketBalance:
    record = session.scalars(
        select(TicketBalance).where(TicketBalance.user_id == user_id).with_for_update()
    ).first()
    if record is None:
        record = TicketBalance(user_id=user_id, balance=0)
        session.add(record)
        session.flush()
    return record


def apply_entry(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    source: str,
    idempotency_key: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> int:
    """Aplica um movimento e devolve o saldo resultante.

    A chave de idempotência garante que repetir a chamada não duplica o efeito.
    """

    if amount == 0:
        raise TicketError("amount_zero")
    existing = session.scalars(
        select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        if existing.user_id != user_id or existing.amount != amount:
            raise TicketConflict("idempotency_key_reused")
        return get_balance(session, user_id)

    balance = _lock_balance(session, user_id)
    new_balance = balance.balance + amount
    if new_balance < 0:
        raise InsufficientTickets

    session.add(
        TicketLedgerEntry(
            user_id=user_id,
            amount=amount,
            source=source,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
        )
    )
    balance.balance = new_balance
    try:
        session.flush()
    except IntegrityError as exc:
        raise TicketConflict("idempotency_key_reused") from exc
    return new_balance


def grant(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    source: str,
    idempotency_key: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> int:
    if amount <= 0:
        raise TicketError("grant_amount_invalid")
    return apply_entry(
        session,
        user_id,
        amount,
        source=source,
        idempotency_key=idempotency_key,
        ref_type=ref_type,
        ref_id=ref_id,
    )


def consume(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    ref_type: str,
    ref_id: uuid.UUID,
) -> int:
    if amount <= 0:
        raise TicketError("consume_amount_invalid")
    return apply_entry(
        session,
        user_id,
        -amount,
        source="consumption",
        idempotency_key=f"consume:{ref_type}:{ref_id}:{user_id}",
        ref_type=ref_type,
        ref_id=ref_id,
    )


def refund(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    ref_type: str,
    ref_id: uuid.UUID,
) -> int:
    if amount <= 0:
        raise TicketError("refund_amount_invalid")
    return apply_entry(
        session,
        user_id,
        amount,
        source="refund",
        idempotency_key=f"refund:{ref_type}:{ref_id}:{user_id}",
        ref_type=ref_type,
        ref_id=ref_id,
    )
