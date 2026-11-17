"""Invariante permanente por evento (ADR 0049 §13.7).

Tickets e caixa são dois saldos independentes:
- compra sobe o caixa pago e o lote em tickets;
- quitação baixa k×310 e k tickets na mesma transação;
- quadra + JOGA fecham k×310;
- nenhum saldo negativo.
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
from app.modules.pricing.service import TICKET_CALIBRATION_CENTS
from app.modules.tickets.models import TicketBalance, TicketLot, TicketLotConsumption
from app.modules.tickets.service import (
    confirm_purchase,
    create_purchase,
    expected_player_credit_cents,
    player_credit_cents,
)
from tests.helpers_results import make_user
from tests.test_ticket_settlement import api_client, bearer, open_booking, setup_context


def test_purchase_raises_cash_and_ticket_lot(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    assert player_credit_cents(db_session, user_id) == purchase.amount_cents
    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None
    assert lot.remaining == purchase.tickets
    assert lot.unit_price_cents == purchase.amount_cents // purchase.tickets
    cached = db_session.get(TicketBalance, user_id)
    assert cached is not None and cached.balance == purchase.tickets
    assert reconcile_credit(db_session).clean


def test_settlement_event_closes_cash_and_tickets(
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
    assert sum(item.tickets_consumed for item in participants) == (
        model.tickets_per_seat or 0
    ) * len(participants)

    ticket_total = sum(item.tickets_consumed * TICKET_CALIBRATION_CENTS for item in participants)
    assert sum(item.fee_charge_cents for item in participants) == (
        ticket_total - model.venue_price_cents
    )
    assert sum(item.contribution_cents for item in participants) == ticket_total

    for participant in participants:
        assert participant.tickets_consumed == model.tickets_per_seat
        assert participant.contribution_cents == (
            participant.tickets_consumed * TICKET_CALIBRATION_CENTS
        )
        amount = db_session.scalar(
            select(func.coalesce(func.sum(TicketLotConsumption.amount), 0)).where(
                TicketLotConsumption.user_id == participant.user_id,
                TicketLotConsumption.ref_id == booking_id,
            )
        )
        assert int(amount or 0) == participant.tickets_consumed

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
        assert player_credit_cents(db_session, participant.user_id) == 0

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
    assert by_code[FEE_REVENUE] == ticket_total - model.venue_price_cents

    report = reconcile_credit(db_session)
    assert report.clean, (report.mismatches, report.balance_mismatches)
    for user_id in context["users"]:
        assert player_credit_cents(db_session, user_id) >= 0
        assert expected_player_credit_cents(db_session, user_id) >= 0
