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

from app.modules.tickets.models import TicketBalance, TicketLedgerEntry


class TicketError(Exception):
    """Erro de carteira de ingressos."""


class InsufficientTickets(TicketError):
    """Saldo insuficiente para a operação."""


class TicketConflict(TicketError):
    """Chave de idempotência reutilizada com efeito diferente."""


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
