"""Invariante permanente do crédito em centavos (ADR 0049 §11.6).

Sem skip. O ticket vale R$ 3,10; `k = ceil(contribution / 310)` é exibição. O
ledger, a cota congelada e o consumo do lote fecham no mesmo evento.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingParticipant
from app.modules.ledger.accounts import FEE_REVENUE, VENUE_PAYABLE_PREFIX, player_credit_code
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.ledger.opening import open_ledger
from app.modules.ledger.reconciliation import reconcile_credit
from app.modules.ledger.service import LedgerService
from app.modules.tickets.models import TicketLotConsumption
from app.modules.tickets.service import (
    TICKET_VALUE_CENTS,
    confirm_purchase,
    create_purchase,
    credit_balance_cents,
    tickets_for_cents,
)
from tests.helpers_results import make_user
from tests.test_ticket_settlement import api_client, bearer, open_booking, setup_context


def test_purchase_credit_matches_lots(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "medio")
    confirm_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    expected = purchase.tickets * TICKET_VALUE_CENTS
    assert credit_balance_cents(db_session, user_id) == expected
    assert LedgerService(db_session).balance_for_code(player_credit_code(user_id)) == expected
    assert reconcile_credit(db_session).clean


def test_settlement_event_closes_cents_and_tickets(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    booking_id = uuid.UUID(booking["id"])
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    transaction = db_session.scalar(
        select(LedgerTransaction).where(
            LedgerTransaction.idempotency_key == f"booking:{booking_id}:confirm"
        )
    )
    assert transaction is not None

    model = db_session.get(Booking, booking_id)
    assert model is not None
    participants = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == booking_id)
    ).all()
    assert participants
    assert sum(item.space_charge_cents for item in participants) == model.venue_price_cents
    assert sum(item.fee_charge_cents for item in participants) == model.fee_cents
    assert sum(item.contribution_cents for item in participants) == model.total_cents

    for participant in participants:
        expected_tickets = tickets_for_cents(participant.contribution_cents)
        assert participant.tickets_consumed == expected_tickets
        amount = db_session.scalar(
            select(func.coalesce(func.sum(TicketLotConsumption.amount_cents), 0)).where(
                TicketLotConsumption.user_id == participant.user_id,
                TicketLotConsumption.ref_id == booking_id,
            )
        )
        tickets = db_session.scalar(
            select(func.coalesce(func.sum(TicketLotConsumption.amount), 0)).where(
                TicketLotConsumption.user_id == participant.user_id,
                TicketLotConsumption.ref_id == booking_id,
            )
        )
        assert int(amount or 0) == participant.contribution_cents
        assert int(tickets or 0) == expected_tickets

        debit = db_session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0))
            .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
            .where(
                LedgerEntry.transaction_id == transaction.id,
                LedgerAccount.code == player_credit_code(participant.user_id),
                LedgerEntry.direction == "D",
            )
        )
        assert int(debit or 0) == participant.contribution_cents

    credits = db_session.execute(
        select(LedgerAccount.code, LedgerEntry.amount_cents)
        .join(LedgerEntry, LedgerEntry.account_id == LedgerAccount.id)
        .where(
            LedgerEntry.transaction_id == transaction.id,
            LedgerEntry.direction == "C",
        )
    ).all()
    by_code = {str(code): int(amount) for code, amount in credits}
    assert by_code[f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}"] == model.venue_price_cents
    assert by_code[FEE_REVENUE] == model.fee_cents

    report = reconcile_credit(db_session)
    assert report.clean, report.mismatches
    for user_id in context["users"]:
        assert credit_balance_cents(db_session, user_id) >= 0
