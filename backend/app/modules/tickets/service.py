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

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User
from app.modules.ledger.accounts import player_credit_code
from app.modules.ledger.models import LedgerAccount
from app.modules.ledger.service import LedgerService
from app.modules.tickets.models import (
    TicketLedgerEntry,
    TicketLot,
    TicketLotConsumption,
    TicketPack,
    TicketPurchase,
)

SOURCE_PRIORITY = {
    "pass": 0,
    "free_level": 1,
    "admin": 2,
    "purchase": 3,
    "refund": 4,
}
GRANT_SOURCES = frozenset({"purchase", "pass", "free_level", "admin", "refund"})
PAID_SOURCES = frozenset({"purchase", "refund"})

logger = logging.getLogger("joga.tickets.balance")


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


class BalanceUnavailable(TicketError):
    """A fonte ledger não tem conta para um saldo que deveria existir."""


class LedgerInconsistency(TicketError):
    """Ledger e lotes divergem; a leitura não pode mascarar."""


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
    _lock_user(session, user_id)
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
    if existing is None and lot is not None:
        lot.remaining = 0
    purchase.status = "cancelled"
    session.flush()
    if existing is None:
        from app.modules.ledger.flow import post_purchase_refund

        post_purchase_refund(session, purchase)
    return _tickets_balance(session, user_id)


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
    unit_price, remainder = divmod(purchase.amount_cents, purchase.tickets)
    if remainder != 0:
        raise TicketError("purchase_unit_price_not_exact")
    balance = grant(
        session,
        user_id,
        purchase.tickets,
        source="purchase",
        idempotency_key=f"purchase:{purchase.id}",
        ref_type="purchase",
        ref_id=purchase.id,
        unit_price_cents=unit_price,
    )
    from app.modules.ledger.flow import post_credit_purchase

    post_credit_purchase(session, purchase, now=purchase.paid_at)
    return purchase, balance


def _paid_lots_tickets(session: Session, user_id: uuid.UUID) -> int:
    value = session.scalar(
        select(func.coalesce(func.sum(TicketLot.remaining), 0)).where(
            TicketLot.user_id == user_id,
            TicketLot.source.in_(PAID_SOURCES),
        )
    )
    return int(value or 0)


def expected_player_credit_cents(session: Session, user_id: uuid.UUID) -> int:
    """Caixa esperado: compras + abertura − consumo de reservas confirmadas.

    O débito de ``player_credit`` acontece quando a reserva confirma
    (``post_booking_confirmed``), não no momento em que cada vaga é quitada.
    Por isso só entram aqui as vagas de reservas com ``confirmed_at``; sem esse
    recorte, uma reserva parcialmente quitada apareceria como divergência.
    """

    from app.modules.bookings.models import Booking, BookingParticipant
    from app.modules.ledger.models import LedgerEntry, LedgerTransaction
    from app.modules.pricing.service import TICKET_CALIBRATION_CENTS

    purchases = session.scalar(
        select(func.coalesce(func.sum(TicketPurchase.amount_cents), 0)).where(
            TicketPurchase.user_id == user_id,
            TicketPurchase.status == "paid",
        )
    )
    opening = session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0))
        .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
        .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
        .where(
            LedgerTransaction.kind == "opening_balance",
            LedgerTransaction.ref_id == user_id,
            LedgerAccount.code == player_credit_code(user_id),
            LedgerEntry.direction == "C",
        )
    )
    consumed_tickets = session.scalar(
        select(func.coalesce(func.sum(BookingParticipant.tickets_consumed), 0))
        .join(Booking, Booking.id == BookingParticipant.booking_id)
        .where(
            BookingParticipant.user_id == user_id,
            BookingParticipant.funding_source == "credit",
            BookingParticipant.payment_status != "REFUNDED",
            Booking.pricing_version != "legacy_v0",
            Booking.confirmed_at.is_not(None),
        )
    )
    return (
        int(purchases or 0)
        + int(opening or 0)
        - int(consumed_tickets or 0) * TICKET_CALIBRATION_CENTS
    )


def usable_non_paid_tickets(
    session: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    """Tickets de passe/grátis/admin utilizáveis no instante informado (sem lock)."""

    moment = ensure_utc(now or utcnow())
    lots = session.scalars(
        select(TicketLot).where(
            TicketLot.user_id == user_id,
            TicketLot.remaining > 0,
            TicketLot.source.in_(("pass", "free_level", "admin")),
            _usable_lot_condition(moment),
        )
    ).all()
    return sum(lot.remaining for lot in lots)


def _tickets_balance(
    session: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    """Soma dos lotes utilizáveis; não valida o caixa em reais."""

    return _paid_lots_tickets(session, user_id) + usable_non_paid_tickets(session, user_id, now=now)


def get_balance(
    session: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    """Saldo exibido em tickets, lido exclusivamente dos lotes.

    Compõe os tickets comprados (lotes) com passe/grátis/admin utilizáveis e
    valida o caixa em `player_credit`. Sem fallback: conta ausente, caixa
    divergente ou saldo negativo falha alto.
    """

    purchased = _paid_lots_tickets(session, user_id)
    account = session.scalar(
        select(LedgerAccount).where(LedgerAccount.code == player_credit_code(user_id))
    )
    if account is None:
        if purchased > 0:
            logger.error("balance_unavailable code=ledger_account_missing")
            raise BalanceUnavailable("ledger_account_missing")
    else:
        ledger_cents = LedgerService(session).balance_cents(account)
        if ledger_cents < 0:
            logger.error("balance_unavailable code=negative_player_credit")
            raise LedgerInconsistency("negative_player_credit")
        expected = expected_player_credit_cents(session, user_id)
        if ledger_cents != expected:
            logger.error(
                "balance_unavailable code=ledger_cash_mismatch ledger=%s expected=%s",
                ledger_cents,
                expected,
            )
            raise LedgerInconsistency("ledger_cash_mismatch")
    return purchased + usable_non_paid_tickets(session, user_id, now=now)


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
        statement = statement.where(
            TicketLot.remaining > 0,
            _usable_lot_condition(utcnow()),
        )
    return session.scalars(
        statement.order_by(TicketLot.expires_at.asc().nulls_last(), TicketLot.created_at)
    ).all()


def current_period(now: datetime) -> str:
    """Competência mensal da franquia do passe (`YYYY-MM`, UTC)."""

    return ensure_utc(now).strftime("%Y-%m")


def _usable_lot_condition(now: datetime) -> ColumnElement[bool]:
    """Condição de lote utilizável (ADR 0049 §9.1).

    - passe: só a competência corrente;
    - comprado/devolução: nunca expira;
    - nível/admin: expira apenas se houver `expires_at`.
    """

    period = current_period(now)
    return or_(
        and_(TicketLot.source == "pass", TicketLot.period == period),
        and_(
            TicketLot.source.in_(("purchase", "refund")),
            TicketLot.expires_at.is_(None),
        ),
        and_(
            TicketLot.source.in_(("free_level", "admin")),
            or_(TicketLot.expires_at.is_(None), TicketLot.expires_at > now),
        ),
    )


def _lot_is_usable(lot: TicketLot, now: datetime) -> bool:
    if lot.source == "pass":
        return lot.period == current_period(now)
    if lot.source in {"purchase", "refund"}:
        return True
    return lot.expires_at is None or ensure_utc(lot.expires_at) > now


def _lock_user(session: Session, user_id: uuid.UUID) -> None:
    """Serializa operações de carteira por jogador.

    A linha de ``users`` é o lock de coordenação; lotes continuam sendo a
    verdade do saldo e não há mais escrita em ``ticket_balances``.
    """

    locked = session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    if locked is None:
        raise TicketError("user_missing")


def _active_lots(session: Session, user_id: uuid.UUID, now: datetime) -> list[TicketLot]:
    rows = list(
        session.scalars(
            select(TicketLot)
            .where(
                TicketLot.user_id == user_id,
                TicketLot.remaining > 0,
                _usable_lot_condition(now),
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
    period: str | None = None,
    unit_price_cents: int | None = None,
) -> int:
    """Aplica um movimento e devolve o saldo resultante.

    A chave de idempotência garante que repetir a chamada não duplica o efeito.
    Créditos sempre criam um lote; débitos consomem lotes ativos na ordem da
    política de origem/validade. O lock é a linha do jogador, não um saldo em
    cache.
    """

    if amount == 0:
        raise TicketError("amount_zero")
    existing = session.scalars(
        select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        if existing.user_id != user_id or existing.amount != amount:
            raise TicketConflict("idempotency_key_reused")
        return _tickets_balance(session, user_id)

    now = utcnow()
    _lock_user(session, user_id)
    if amount > 0:
        if source not in GRANT_SOURCES:
            raise TicketError("invalid_grant_source")
        if source == "pass" and not period:
            raise TicketError("pass_period_required")
        if source != "pass" and period is not None:
            raise TicketError("period_only_for_pass")
        if source in PAID_SOURCES:
            if unit_price_cents is None:
                # Chamadas de teste/legado sem compra explícita usam o calibre.
                unit_price_cents = 310
            if unit_price_cents <= 0:
                raise TicketError("unit_price_invalid")
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
                unit_price_cents=(unit_price_cents if source in PAID_SOURCES else None),
                period=period,
                expires_at=expires_at,
                ref_type=ref_type,
                ref_id=ref_id,
                ledger_entry_id=ledger.id,
            )
        )
    else:
        need = -amount
        lots = _active_lots(session, user_id, now)
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
        if remaining != 0:
            raise InsufficientTickets

    try:
        session.flush()
    except IntegrityError as exc:
        raise TicketConflict("idempotency_key_reused") from exc
    return _tickets_balance(session, user_id)


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
    period: str | None = None,
    unit_price_cents: int | None = None,
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
        period=period,
        unit_price_cents=unit_price_cents,
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
        return _tickets_balance(session, user_id)

    now = utcnow()
    _lock_user(session, user_id)
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
            if lot is None or not _lot_is_usable(lot, now):
                continue
            capacity = lot.original_amount - lot.remaining
            quantity = min(consumption.amount, requested, capacity)
            if quantity <= 0:
                continue
            lot.remaining += quantity
            requested -= quantity
            restored += quantity
        if restored == 0:
            return _tickets_balance(session, user_id)
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
        price = session.scalar(
            select(func.max(TicketLot.unit_price_cents)).where(
                TicketLot.user_id == user_id,
                TicketLot.source.in_(PAID_SOURCES),
                TicketLot.unit_price_cents.is_not(None),
            )
        )
        session.add(
            TicketLot(
                user_id=user_id,
                source="refund",
                original_amount=restored,
                remaining=restored,
                unit_price_cents=int(price) if price is not None else None,
                ref_type=ref_type,
                ref_id=ref_id,
                ledger_entry_id=ledger.id,
            )
        )
    session.flush()
    return _tickets_balance(session, user_id)


def player_credit_cents(session: Session, user_id: uuid.UUID) -> int:
    """Saldo monetário de `player_credit`; zero quando a conta não existe."""

    account = session.scalar(
        select(LedgerAccount).where(LedgerAccount.code == player_credit_code(user_id))
    )
    if account is None:
        return 0
    return max(0, LedgerService(session).balance_cents(account))


def _paid_lots(session: Session, user_id: uuid.UUID) -> list[TicketLot]:
    """Lotes comprados/devolução com tickets, na ordem de consumo."""

    return list(
        session.scalars(
            select(TicketLot)
            .where(
                TicketLot.user_id == user_id,
                TicketLot.source.in_(PAID_SOURCES),
                TicketLot.remaining > 0,
            )
            .order_by(TicketLot.created_at, TicketLot.id)
            .with_for_update()
        ).all()
    )


def paid_tickets_available(session: Session, user_id: uuid.UUID) -> int:
    value = session.scalar(
        select(func.coalesce(func.sum(TicketLot.remaining), 0)).where(
            TicketLot.user_id == user_id,
            TicketLot.source.in_(PAID_SOURCES),
        )
    )
    return int(value or 0)


def consume_paid_tickets(
    session: Session,
    user_id: uuid.UUID,
    tickets: int,
    *,
    ref_type: str,
    ref_id: uuid.UUID,
) -> int:
    """Baixa `tickets` dos lotes comprados/devolução, sem tocar passe/grátis."""

    if tickets <= 0:
        raise TicketError("consume_amount_invalid")
    key = f"consume:{ref_type}:{ref_id}:{user_id}"
    existing = session.scalars(
        select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == key)
    ).first()
    if existing is not None:
        return _tickets_balance(session, user_id)

    _lock_user(session, user_id)
    lots = _paid_lots(session, user_id)
    if sum(lot.remaining for lot in lots) < tickets:
        raise InsufficientTickets

    ledger = TicketLedgerEntry(
        user_id=user_id,
        amount=-tickets,
        source="consumption",
        ref_type=ref_type,
        ref_id=ref_id,
        idempotency_key=key,
    )
    session.add(ledger)
    session.flush()

    remaining = tickets
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
                ref_type=ref_type,
                ref_id=ref_id,
                ledger_entry_id=ledger.id,
            )
        )
        remaining -= take
        if remaining == 0:
            break
    if remaining != 0:
        raise InsufficientTickets

    session.flush()
    return _tickets_balance(session, user_id)


def non_paid_tickets_available(session: Session, user_id: uuid.UUID) -> tuple[int, str | None]:
    """Tickets de passe/grátis/admin disponíveis e a primeira origem."""

    total = 0
    source: str | None = None
    for lot in _active_lots(session, user_id, utcnow()):
        if lot.source in PAID_SOURCES:
            continue
        total += lot.remaining
        if source is None:
            source = lot.source
    return total, source


def expire_due(session: Session, *, now: datetime | None = None) -> int:
    """Expira lotes vencidos e reduz o saldo. Idempotente por lote.

    Passe vence por competência (`period`), não por `expires_at`. Crédito
    comprado e devolução nunca expiram; nível/admin seguem `expires_at`.
    """

    moment = ensure_utc(now or utcnow())
    period = current_period(moment)
    due_before = or_(
        and_(
            TicketLot.source == "pass",
            or_(TicketLot.period.is_(None), TicketLot.period < period),
        ),
        and_(
            TicketLot.source.in_(("free_level", "admin")),
            TicketLot.expires_at.is_not(None),
            TicketLot.expires_at <= moment,
        ),
    )
    user_ids = list(
        session.scalars(
            select(TicketLot.user_id).where(TicketLot.remaining > 0, due_before).distinct()
        ).all()
    )
    expired = 0
    for user_id in sorted(user_ids, key=str):
        _lock_user(session, user_id)
        lots = list(
            session.scalars(
                select(TicketLot)
                .where(
                    TicketLot.user_id == user_id,
                    TicketLot.remaining > 0,
                    due_before,
                )
                .with_for_update()
            ).all()
        )
        for lot in lots:
            key = f"expire:{lot.id}"
            existing = session.scalars(
                select(TicketLedgerEntry).where(TicketLedgerEntry.idempotency_key == key)
            ).first()
            if existing is not None:
                lot.remaining = 0
                continue
            amount = lot.remaining
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
            expired += 1
    session.flush()
    return expired
