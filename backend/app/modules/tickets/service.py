"""Operações da carteira de ingressos (ADR 0042 §2).

Regras:
- todo movimento é evento no ledger append-only, com chave de idempotência;
- cada crédito cria um lote com origem e validade;
- o consumo usa primeiro a franquia do passe, depois ingressos de nível e por
  último os comprados;
- lotes expirados permanecem no histórico, mas não contam no saldo;
- o saldo é projeção e nunca pode ficar negativo.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.tickets.models import (
    TicketBalance,
    TicketLedgerEntry,
    TicketLot,
    TicketLotConsumption,
    TicketPack,
    TicketPurchase,
)

SOURCE_PRIORITY = {
    "pass": 0,
    "free_level": 1,
    "purchase": 2,
    "refund": 3,
    "admin": 4,
}
GRANT_SOURCES = frozenset({"purchase", "pass", "free_level", "admin", "refund"})


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
        select(TicketPack).where(TicketPack.active.is_(True)).order_by(TicketPack.tickets.asc())
    ).all()


def get_pack(session: Session, code: str) -> TicketPack:
    pack = session.scalars(
        select(TicketPack).where(TicketPack.code == code, TicketPack.active.is_(True))
    ).first()
    if pack is None:
        raise PackNotFound
    return pack


def create_purchase(session: Session, user_id: uuid.UUID, pack_code: str) -> TicketPurchase:
    """Registra a intenção de compra. Idempotente enquanto houver pendência."""

    pack = get_pack(session, pack_code)
    existing = session.scalars(
        select(TicketPurchase)
        .where(
            TicketPurchase.user_id == user_id,
            TicketPurchase.pack_id == pack.id,
            TicketPurchase.status == "pending",
        )
        .order_by(TicketPurchase.created_at.desc(), TicketPurchase.id.desc())
    ).first()
    if existing is not None:
        return existing

    purchase = TicketPurchase(
        user_id=user_id,
        pack_id=pack.id,
        tickets=pack.tickets,
        amount_cents=pack.amount_cents,
    )
    try:
        with session.begin_nested():
            session.add(purchase)
            session.flush()
    except IntegrityError:
        concurrent = session.scalars(
            select(TicketPurchase)
            .where(
                TicketPurchase.user_id == user_id,
                TicketPurchase.pack_id == pack.id,
                TicketPurchase.status == "pending",
            )
            .order_by(TicketPurchase.created_at.desc(), TicketPurchase.id.desc())
        ).first()
        if concurrent is not None:
            return concurrent
        raise
    return purchase


def revoke_purchase(session: Session, user_id: uuid.UUID, purchase_id: uuid.UUID) -> int:
    """Revoga o crédito ainda não consumido de uma compra reembolsada."""

    purchase = session.get(TicketPurchase, purchase_id)
    if purchase is None or purchase.user_id != user_id:
        raise PurchaseNotFound
    balance = _lock_balance(session, user_id)
    lot = session.scalars(
        select(TicketLot)
        .where(
            TicketLot.user_id == user_id,
            TicketLot.source == "purchase",
            TicketLot.ref_type == "purchase",
            TicketLot.ref_id == purchase.id,
        )
        .with_for_update()
    ).first()
    amount = lot.remaining if lot is not None else 0
    key = f"purchase_refund:{purchase.id}"
    existing = session.scalars(
        select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == key)
    ).first()
    if amount > 0 and existing is None:
        assert lot is not None
        ledger = TicketLedgerEntry(
            user_id=user_id,
            amount=-amount,
            source="refund",
            ref_type="purchase_refund",
            ref_id=purchase.id,
            idempotency_key=key,
        )
        session.add(ledger)
        session.flush()
        lot.remaining = 0
        balance.balance -= amount
    purchase.status = "cancelled"
    session.flush()
    return balance.balance


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


def list_lots(
    session: Session,
    user_id: uuid.UUID,
    *,
    include_expired: bool = False,
) -> Sequence[TicketLot]:
    """Lotes do jogador; por padrão retorna apenas os ainda utilizáveis."""

    statement = select(TicketLot).where(TicketLot.user_id == user_id)
    if not include_expired:
        now = utcnow()
        statement = statement.where(
            TicketLot.remaining > 0,
            or_(TicketLot.expires_at.is_(None), TicketLot.expires_at > now),
        )
    return session.scalars(
        statement.order_by(TicketLot.expires_at.asc().nulls_last(), TicketLot.created_at)
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


def _active_lots(session: Session, user_id: uuid.UUID, now: datetime) -> list[TicketLot]:
    rows = list(
        session.scalars(
            select(TicketLot)
            .where(
                TicketLot.user_id == user_id,
                TicketLot.remaining > 0,
                or_(TicketLot.expires_at.is_(None), TicketLot.expires_at > now),
            )
            .with_for_update()
        ).all()
    )
    return sorted(
        rows,
        key=lambda lot: (
            SOURCE_PRIORITY.get(lot.source, 9),
            lot.expires_at is None,
            ensure_utc(lot.expires_at) if lot.expires_at is not None else datetime.max,
            lot.created_at,
            str(lot.id),
        ),
    )


def _legacy_lot(session: Session, user_id: uuid.UUID, balance: int) -> TicketLot:
    """Cria lote administrativo para saldo anterior à introdução dos lotes."""

    ledger = TicketLedgerEntry(
        user_id=user_id,
        amount=balance,
        source="admin",
        ref_type="legacy_balance",
        ref_id=None,
        idempotency_key=f"legacy_lot:{user_id}:{balance}",
    )
    session.add(ledger)
    session.flush()
    lot = TicketLot(
        user_id=user_id,
        source="admin",
        original_amount=balance,
        remaining=balance,
        ledger_entry_id=ledger.id,
        ref_type="legacy_balance",
    )
    session.add(lot)
    session.flush()
    return lot


def apply_entry(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    source: str,
    idempotency_key: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> int:
    """Aplica um movimento e devolve o saldo resultante.

    A chave de idempotência garante que repetir a chamada não duplica o efeito.
    Créditos sempre criam um lote; débitos consomem lotes ativos na ordem da
    política de origem/validade.
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

    now = utcnow()
    balance = _lock_balance(session, user_id)
    if amount > 0:
        if source not in GRANT_SOURCES:
            raise TicketError("invalid_grant_source")
        ledger = TicketLedgerEntry(
            user_id=user_id,
            amount=amount,
            source=source,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
        )
        session.add(ledger)
        session.flush()
        session.add(
            TicketLot(
                user_id=user_id,
                source=source,
                original_amount=amount,
                remaining=amount,
                expires_at=expires_at,
                ref_type=ref_type,
                ref_id=ref_id,
                ledger_entry_id=ledger.id,
            )
        )
        balance.balance += amount
    else:
        need = -amount
        if balance.balance < need:
            raise InsufficientTickets
        lots = _active_lots(session, user_id, now)
        if not lots and balance.balance > 0:
            lots = [_legacy_lot(session, user_id, balance.balance)]
        if sum(lot.remaining for lot in lots) < need:
            raise InsufficientTickets
        ledger = TicketLedgerEntry(
            user_id=user_id,
            amount=amount,
            source=source,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
        )
        session.add(ledger)
        session.flush()
        remaining = need
        for lot in lots:
            take = min(lot.remaining, remaining)
            if take <= 0:
                continue
            lot.remaining -= take
            session.add(
                TicketLotConsumption(
                    lot_id=lot.id,
                    user_id=user_id,
                    amount=take,
                    ref_type=ref_type or source,
                    ref_id=ref_id or ledger.id,
                    ledger_entry_id=ledger.id,
                )
            )
            remaining -= take
            if remaining == 0:
                break
        balance.balance -= need

    try:
        session.flush()
    except IntegrityError as exc:
        raise TicketConflict("idempotency_key_reused") from exc
    return balance.balance


def grant(
    session: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    source: str,
    idempotency_key: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
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
        expires_at=expires_at,
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
    """Devolve ingressos ao lote original, quando ele ainda está válido.

    Ingressos de passe/franquia expirados não viram ingressos comprados: o
    crédito só é aplicado a lotes ativos. Sem movimentos de consumo (saldo
    legado), cria um lote de devolução sem validade.
    """

    if amount <= 0:
        raise TicketError("refund_amount_invalid")
    key = f"refund:{ref_type}:{ref_id}:{user_id}"
    existing = session.scalars(
        select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == key)
    ).first()
    if existing is not None:
        return get_balance(session, user_id)

    now = utcnow()
    balance = _lock_balance(session, user_id)
    lookup_type = "booking" if ref_type == "booking_cancel" else ref_type
    consumptions = list(
        session.scalars(
            select(TicketLotConsumption)
            .where(
                TicketLotConsumption.user_id == user_id,
                TicketLotConsumption.ref_type.in_({lookup_type, ref_type}),
                TicketLotConsumption.ref_id == ref_id,
            )
            .with_for_update()
        ).all()
    )

    restored = 0
    if consumptions:
        requested = amount
        for consumption in consumptions:
            if requested <= 0:
                break
            lot = session.scalars(
                select(TicketLot).where(TicketLot.id == consumption.lot_id).with_for_update()
            ).first()
            if lot is None or (lot.expires_at is not None and ensure_utc(lot.expires_at) <= now):
                continue
            capacity = lot.original_amount - lot.remaining
            quantity = min(consumption.amount, requested, capacity)
            if quantity <= 0:
                continue
            lot.remaining += quantity
            requested -= quantity
            restored += quantity
        if restored == 0:
            return balance.balance
    else:
        restored = amount

    ledger = TicketLedgerEntry(
        user_id=user_id,
        amount=restored,
        source="refund",
        ref_type=ref_type,
        ref_id=ref_id,
        idempotency_key=key,
    )
    session.add(ledger)
    if not consumptions:
        session.flush()
        session.add(
            TicketLot(
                user_id=user_id,
                source="refund",
                original_amount=restored,
                remaining=restored,
                ref_type=ref_type,
                ref_id=ref_id,
                ledger_entry_id=ledger.id,
            )
        )
    balance.balance += restored
    session.flush()
    return balance.balance


def expire_due(session: Session, *, now: datetime | None = None) -> int:
    """Expira lotes vencidos e reduz o saldo. Idempotente por lote."""

    moment = ensure_utc(now or utcnow())
    lots = list(
        session.scalars(
            select(TicketLot)
            .where(
                TicketLot.remaining > 0,
                TicketLot.expires_at.is_not(None),
                TicketLot.expires_at <= moment,
            )
            .with_for_update()
        ).all()
    )
    expired = 0
    for lot in lots:
        key = f"expire:{lot.id}"
        existing = session.scalars(
            select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == key)
        ).first()
        if existing is not None:
            lot.remaining = 0
            continue
        balance = _lock_balance(session, lot.user_id)
        amount = lot.remaining
        if balance.balance < amount:
            raise TicketError("balance_inconsistent")
        session.add(
            TicketLedgerEntry(
                user_id=lot.user_id,
                amount=-amount,
                source="expired",
                ref_type="ticket_lot",
                ref_id=lot.id,
                idempotency_key=key,
            )
        )
        lot.remaining = 0
        balance.balance -= amount
        expired += 1
    session.flush()
    return expired
