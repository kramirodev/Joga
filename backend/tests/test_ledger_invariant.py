"""Invariante permanente do crédito em reais (ADR 0049 §9.1/§9.2).

A rede de segurança da 14E: depois de qualquer mutação de crédito, o saldo de
`player_credit:<user>` no ledger deve ser igual à soma dos lotes de compra
(remaining × preço unitário efetivamente pago), mais os lotes de devolução
rastreados ao mesmo preço.

Enquanto a sombra de escrita do ledger não estiver ligada (14E.1), não existe
lançamento para comparar. O teste fica explicitamente ignorado e precisa ser
habilitado na Etapa 6.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ledger.accounts import player_credit_code
from app.modules.ledger.service import LedgerError, LedgerService
from app.modules.tickets.models import TicketLot, TicketPurchase

pytestmark = pytest.mark.skip(
    reason="14E.1: ledger ainda não é escrito pelos fluxos; habilitar na Etapa 6"
)


def expected_purchased_credit_cents(session: Session, user_id: uuid.UUID) -> int:
    """Crédito esperado dos lotes de compra, pelo preço pago no lote."""

    rows = session.execute(
        select(TicketLot, TicketPurchase)
        .join(TicketPurchase, TicketPurchase.id == TicketLot.ref_id)
        .where(
            TicketLot.user_id == user_id,
            TicketLot.source == "purchase",
            TicketLot.remaining > 0,
        )
    ).all()
    total = 0
    for lot, purchase in rows:
        if purchase.tickets <= 0 or purchase.amount_cents % purchase.tickets != 0:
            raise AssertionError("preço unitário não é divisão exata")
        total += lot.remaining * (purchase.amount_cents // purchase.tickets)
    return total


def ledger_credit_cents(session: Session, user_id: uuid.UUID) -> int:
    service = LedgerService(session)
    try:
        return service.balance_for_code(player_credit_code(user_id))
    except LedgerError:
        return 0


def assert_credit_invariant(session: Session, user_id: uuid.UUID) -> None:
    assert ledger_credit_cents(session, user_id) == expected_purchased_credit_cents(
        session, user_id
    )


def test_credit_ledger_matches_purchased_lots(db_session: Session) -> None:
    """Habilitado na Etapa 6, quando os fluxos passarem a lançar no ledger."""

    from app.modules.tickets.service import grant
    from tests.helpers_results import make_user

    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        10,
        source="purchase",
        idempotency_key=f"invariant:{user_id}",
    )
    db_session.flush()
    assert_credit_invariant(db_session, user_id)
