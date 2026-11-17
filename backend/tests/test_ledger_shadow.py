"""Sombra de escrita do ledger (ADR 0049 §11).

Nenhuma leitura pública depende destes lançamentos. Os testes verificam o
evento, o balanceamento, a idempotência e a reconciliação por usuário.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingParticipant
from app.modules.bookings.service import BookingService
from app.modules.identity.clock import ensure_utc
from app.modules.ledger.accounts import (
    BANK,
    FEE_REVENUE,
    PASS_DEFERRED_REVENUE,
    PASS_REVENUE,
    PURCHASE_PREMIUM_DEFERRED,
    VENUE_PAYABLE_PREFIX,
    player_credit_code,
)
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.ledger.opening import open_ledger
from app.modules.ledger.reconciliation import reconcile_credit
from app.modules.ledger.service import LedgerService
from app.modules.passes.service import activate_subscription, create_subscription
from app.modules.payments.financial import FinancialService
from app.modules.payments.models import VenueRelease
from app.modules.tickets.models import TicketLot, TicketLotConsumption
from app.modules.tickets.service import (
    TICKET_VALUE_CENTS,
    confirm_purchase,
    consume_credit,
    create_purchase,
    credit_balance_cents,
    grant,
    revoke_purchase,
)
from tests.helpers_results import make_user
from tests.test_ticket_settlement import (
    PRICE_CENTS,
    TICKETS_PER_SEAT,
    api_client,
    bearer,
    open_booking,
    setup_context,
)


def transaction(session: Session, key: str) -> LedgerTransaction:
    row = session.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key))
    assert row is not None, key
    return row


def entries(session: Session, tx: LedgerTransaction) -> dict[tuple[str, str], int]:
    rows = session.execute(
        select(LedgerAccount.code, LedgerEntry.direction, LedgerEntry.amount_cents)
        .join(LedgerEntry, LedgerEntry.account_id == LedgerAccount.id)
        .where(LedgerEntry.transaction_id == tx.id)
    ).all()
    result: dict[tuple[str, str], int] = {}
    for code, direction, amount in rows:
        result[(str(code), str(direction))] = int(amount)
    return result


def test_purchase_separates_credit_and_premium(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    service = LedgerService(db_session)
    credit = purchase.tickets * TICKET_VALUE_CENTS
    premium = purchase.amount_cents - credit
    assert credit == 930
    assert premium == 180
    assert service.balance_for_code("psp_clearing") == purchase.amount_cents
    assert service.balance_for_code(player_credit_code(user_id)) == credit
    assert service.balance_for_code(PURCHASE_PREMIUM_DEFERRED) == premium
    assert credit_balance_cents(db_session, user_id) == credit

    report = reconcile_credit(db_session)
    assert report.clean


def test_booking_confirmation_posts_rule_4(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    booking_id = uuid.UUID(booking["id"])
    participants = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == booking_id)
    ).all()
    assert {item.funding_source for item in participants} == {"credit"}
    assert {item.tickets_consumed for item in participants} == {TICKETS_PER_SEAT}

    tx = transaction(db_session, f"booking:{booking_id}:confirm")
    posted = entries(db_session, tx)
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == PRICE_CENTS
    assert posted[(FEE_REVENUE, "C")] == 2_400
    for participant in participants:
        assert (
            posted[(player_credit_code(participant.user_id), "D")] == participant.contribution_cents
        )
        consumed = db_session.scalar(
            select(TicketLotConsumption.amount_cents)
            .where(
                TicketLotConsumption.user_id == participant.user_id,
                TicketLotConsumption.ref_id == booking_id,
            )
            .order_by(TicketLotConsumption.created_at)
        )
        assert consumed is not None

    service = LedgerService(db_session)
    for user_id in context["users"]:
        assert service.balance_for_code(player_credit_code(user_id)) == 80
        assert credit_balance_cents(db_session, user_id) == 80

    report = reconcile_credit(db_session)
    assert report.clean, report.mismatches


def test_booking_refund_restores_credit(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    BookingService(db_session).cancel(
        context["users"][0],
        uuid.UUID(booking["id"]),
        reason="teste de devolução",
    )
    db_session.flush()

    tx = transaction(db_session, f"booking:{booking['id']}:refund")
    posted = entries(db_session, tx)
    assert posted[(FEE_REVENUE, "D")] == 2_000
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "D")] == 10_000
    canceller = context["users"][0]
    for user_id in context["users"]:
        if user_id == canceller:
            assert (player_credit_code(user_id), "C") not in posted
            assert credit_balance_cents(db_session, user_id) == 80
            continue
        assert posted[(player_credit_code(user_id), "C")] == 2_400
        assert credit_balance_cents(db_session, user_id) == TICKETS_PER_SEAT * 310

    assert reconcile_credit(db_session).clean


def test_release_posts_rule_5(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    for token in context["tokens"]:
        api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )

    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(booking["id"]))
    )
    assert release is not None
    FinancialService(db_session).release_due(
        now=ensure_utc(release.eligible_at) + timedelta(minutes=1)
    )
    db_session.flush()

    posted = entries(db_session, transaction(db_session, f"release:{release.id}"))
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "D")] == PRICE_CENTS
    assert posted[(BANK, "C")] == PRICE_CENTS


def test_purchase_reversal_posts_premium_and_receivable(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, purchase.id)
    revoke_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    posted = entries(db_session, transaction(db_session, f"purchase_refund:{purchase.id}"))
    credit = purchase.tickets * TICKET_VALUE_CENTS
    assert posted[("psp_clearing", "C")] == purchase.amount_cents
    assert posted[(player_credit_code(user_id), "D")] == credit
    assert posted[(PURCHASE_PREMIUM_DEFERRED, "D")] == purchase.amount_cents - credit
    assert credit_balance_cents(db_session, user_id) == 0
    assert reconcile_credit(db_session).clean


def test_pix_confirmation_uses_psp_clearing(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_bookings_api import setup_booking
    from tests.test_payments_service import accepted_booking, pay_all

    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])

    booking_id = uuid.UUID(accepted["id"])
    posted = entries(db_session, transaction(db_session, f"booking:{booking_id}:confirm"))
    assert posted[("psp_clearing", "D")] == 48_000
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == 40_000
    assert posted[(FEE_REVENUE, "C")] == 8_000


def test_pass_sale_and_month_posts(
    db_session: Session,
) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(
        db_session, user_id, "time", now=datetime(2026, 11, 13, 12, tzinfo=UTC)
    )
    activate_subscription(db_session, subscription.id, now=datetime(2026, 11, 13, 12, tzinfo=UTC))
    db_session.flush()

    sale = entries(db_session, transaction(db_session, f"pass:{subscription.id}:sale"))
    assert sale[("psp_clearing", "D")] == subscription.amount_cents
    assert sale[(PASS_DEFERRED_REVENUE, "C")] == subscription.amount_cents

    month = entries(db_session, transaction(db_session, f"pass:{subscription.id}:month:1"))
    monthly = subscription.amount_cents // 3
    assert month[(PASS_DEFERRED_REVENUE, "D")] == monthly
    assert month[(PASS_REVENUE, "C")] == monthly


def test_reconciler_lists_non_credit_seat_as_excluded(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    user_id = context["users"][0]
    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None
    lot.remaining = 0
    lot.remaining_cents = 0
    grant(
        db_session,
        user_id,
        TICKETS_PER_SEAT,
        source="pass",
        idempotency_key=f"pass:test:{user_id}",
        period=datetime.now(UTC).strftime("%Y-%m"),
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    report = reconcile_credit(db_session)
    assert report.clean
    excluded = {item.participant_id for item in report.excluded_seats}
    participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == uuid.UUID(booking["id"]),
            BookingParticipant.user_id == user_id,
        )
    )
    assert participant is not None
    assert participant.funding_source == "pass"
    assert participant.id in excluded


def test_consumption_across_lots_keeps_k_exact(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(db_session, user_id, 1, source="purchase", idempotency_key="lot:1")
    grant(db_session, user_id, 1, source="purchase", idempotency_key="lot:2")
    consume_credit(
        db_session,
        user_id,
        240,
        1,
        ref_type="booking",
        ref_id=uuid.uuid4(),
    )
    ref = uuid.uuid4()
    consume_credit(
        db_session,
        user_id,
        100,
        1,
        ref_type="booking",
        ref_id=ref,
    )
    rows = db_session.execute(
        select(TicketLotConsumption.amount_cents, TicketLotConsumption.amount).where(
            TicketLotConsumption.ref_id == ref
        )
    ).all()
    assert sum(int(row[0] or 0) for row in rows) == 100
    assert sum(int(row[1]) for row in rows) == 1


def test_opening_is_idempotent(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        TICKETS_PER_SEAT,
        source="purchase",
        idempotency_key=f"open:test:{user_id}",
    )
    db_session.flush()

    first = open_ledger(db_session, dry_run=False)
    db_session.flush()
    second = open_ledger(db_session, dry_run=False)
    assert first.created == 1
    assert second.created == 0
    assert LedgerService(db_session).balance_for_code(player_credit_code(user_id)) == (
        TICKETS_PER_SEAT * TICKET_VALUE_CENTS
    )
