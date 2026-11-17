"""Testes da interface financeira, liberações e conciliação (Fase 15)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import Booking
from app.modules.fiscal.models import FiscalDocument
from app.modules.identity.clock import utcnow
from app.modules.identity.models import AuditLog
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.organizations.models import OrganizationMembership
from app.modules.organizations.permissions import Role
from app.modules.payments.financial import (
    DisputeConflict,
    DisputeStateError,
    FinancialService,
    OperatorNotAuthorized,
)
from app.modules.payments.models import FinancialDispute, VenueRelease
from app.modules.payments.reconciliation import reconcile
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import api_client, bearer, setup_booking
from tests.test_payments_service import accepted_booking, pay_all


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def complete_booking(api, context) -> tuple[dict, dict]:
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])
    response = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/complete",
        headers=bearer(context["tokens"][0]),
    )
    assert response.status_code == 200, response.text
    return accepted, response.json()


def test_completion_schedules_release_without_paying_immediately(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, completed = complete_booking(api, context)
    booking_id = uuid.UUID(accepted["id"])
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "COMPLETED"

    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None
    assert release.status == "PENDING"
    assert release.amount_cents == 40_000
    assert aware(release.eligible_at) == aware(booking.starts_at) + timedelta(hours=2)

    ledger_count = db_session.scalar(
        select(func.count())
        .select_from(LedgerTransaction)
        .where(
            LedgerTransaction.ref_type == "venue_release",
            LedgerTransaction.ref_id == release.id,
            LedgerTransaction.kind == "venue_release",
        )
    )
    assert ledger_count == 0

    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["released_cents"] == 0
    assert summary.json()["pending_release_cents"] == 40_000
    assert summary.json()["disputed_cents"] == 0

    receivables = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/receivables",
        headers=bearer(context["tokens"][0]),
    )
    assert receivables.status_code == 200, receivables.text
    body = receivables.json()["receivables"]
    assert receivables.json()["total"] == 1
    assert len(body) == 1
    assert body[0]["status"] == "PENDING"
    assert body[0]["amount_cents"] == 40_000
    assert body[0]["has_open_dispute"] is False
    assert body[0]["booking_id"] == accepted["id"]
    assert completed["status"] == "COMPLETED"

    filtered = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/receivables?status=RELEASED",
        headers=bearer(context["tokens"][0]),
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["receivables"] == []
    assert filtered.json()["total"] == 0


def test_release_is_idempotent_and_only_after_eligibility(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    booking_id = uuid.UUID(accepted["id"])
    service = FinancialService(db_session)
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None

    assert service.release_due(now=aware(release.eligible_at) - timedelta(minutes=1)) == 0
    db_session.commit()
    assert db_session.get(VenueRelease, release.id).status == "PENDING"

    assert service.release_due(now=aware(release.eligible_at) + timedelta(minutes=1)) == 1
    db_session.commit()
    db_session.refresh(release)
    assert release.status == "RELEASED"
    assert release.released_at is not None
    transaction = db_session.scalar(
        select(LedgerTransaction).where(
            LedgerTransaction.idempotency_key == f"release:{release.id}"
        )
    )
    assert transaction is not None
    assert transaction.kind == "venue_release"

    statement = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/statement",
        headers=bearer(context["tokens"][0]),
    )
    assert statement.status_code == 200, statement.text
    types = [entry["entry_type"] for entry in statement.json()["entries"]]
    assert "VENUE_RELEASE" in types
    assert "CHARGE_CREATED" not in types

    assert service.release_due(now=aware(release.eligible_at) + timedelta(days=2)) == 0
    db_session.commit()
    assert reconcile(db_session) == []

    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.json()["released_cents"] == 40_000
    assert summary.json()["pending_release_cents"] == 0


def test_open_dispute_blocks_release_until_decision(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    booking_id = uuid.UUID(accepted["id"])
    organization_id = context["organization"].id
    service = FinancialService(db_session)
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None

    created = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
        json={
            "booking_id": accepted["id"],
            "reason": "Valor da reserva divergente",
            "evidence": "Comprovante interno",
        },
    )
    assert created.status_code == 201, created.text
    dispute = created.json()
    assert dispute["status"] == "OPEN"
    assert dispute["amount_cents"] == 40_000
    db_session.expire_all()
    stored = db_session.get(VenueRelease, release.id)
    assert stored is not None
    assert dispute["deadline_at"] == aware(stored.dispute_deadline).isoformat().replace(
        "+00:00", ""
    )

    duplicate = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
        json={"booking_id": accepted["id"], "reason": "Duplicada"},
    )
    assert duplicate.status_code == 409

    assert service.release_due(now=aware(release.eligible_at) + timedelta(hours=1)) == 0
    db_session.commit()
    assert db_session.get(VenueRelease, release.id).status == "PENDING"
    summary = api.get(
        f"/api/v1/organizations/{organization_id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.json()["disputed_cents"] == 40_000

    with pytest.raises(OperatorNotAuthorized):
        service.decide_dispute(
            uuid.UUID(dispute["id"]),
            operator="intruso",
            decision="ACCEPTED",
            reason="Tentativa",
            authorized_operators=frozenset({"operador-1"}),
        )
    db_session.rollback()

    decided = service.decide_dispute(
        uuid.UUID(dispute["id"]),
        operator="operador-1",
        decision="ACCEPTED",
        reason="Contestação procedente",
        authorized_operators=frozenset({"operador-1"}),
    )
    db_session.commit()
    assert decided.status == "ACCEPTED"
    assert decided.decided_by == "operador-1"
    assert db_session.get(VenueRelease, release.id).status == "RELEASED"
    assert reconcile(db_session) == []

    with pytest.raises(DisputeStateError):
        service.decide_dispute(
            uuid.UUID(dispute["id"]),
            operator="operador-1",
            decision="REJECTED",
            reason="Repetição",
            authorized_operators=frozenset({"operador-1"}),
        )
    db_session.rollback()

    listed = api.get(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["disputes"][0]["status"] == "ACCEPTED"


def test_financial_authorization_is_scoped_by_organization(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    organization_id = context["organization"].id
    accepted, _ = complete_booking(api, context)

    db_session.add(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=context["users"][1],
            role=Role.OPERATOR.value,
        )
    )
    db_session.flush()
    operator_token = make_token(db_session, context["users"][1])

    readable = api.get(
        f"/api/v1/organizations/{organization_id}/financial/receivables",
        headers=bearer(operator_token),
    )
    assert readable.status_code == 200, readable.text

    denied = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(operator_token),
        json={"booking_id": accepted["id"], "reason": "Sem permissão"},
    )
    assert denied.status_code == 403

    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)
    hidden = api.get(
        f"/api/v1/organizations/{organization_id}/financial/statement",
        headers=bearer(outsider_token),
    )
    assert hidden.status_code == 404


def test_statement_and_reconciliation_detect_divergence(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id

    statement = api.get(
        f"/api/v1/organizations/{organization_id}/financial/statement",
        headers=bearer(context["tokens"][0]),
    )
    assert statement.status_code == 200, statement.text
    types = [entry["entry_type"] for entry in statement.json()["entries"]]
    assert statement.json()["total"] >= len(types)
    assert "CHARGE_CREATED" not in types
    assert "PAYMENT_CONFIRMED" in types

    # Divergência simulada: liberação marcada como paga sem transação contábil.
    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(accepted["id"]))
    )
    assert release is not None
    release.status = "RELEASED"
    release.released_at = utcnow()
    db_session.commit()

    issues = reconcile(db_session)
    assert any(issue["code"] == "release_without_ledger_entry" for issue in issues)


def test_dispute_conflict_is_idempotent_at_service_level(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    service = FinancialService(db_session)
    kwargs = {
        "actor_user_id": context["users"][0],
        "organization_id": context["organization"].id,
        "booking_id": uuid.UUID(accepted["id"]),
        "reason": "Conferência",
    }
    first = service.open_dispute(**kwargs)
    db_session.commit()
    assert first.status == "OPEN"
    with pytest.raises(DisputeConflict):
        service.open_dispute(**kwargs)
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(FinancialDispute)) == 1


def test_statement_and_receivables_expose_two_line_pricing(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id
    booking_id = uuid.UUID(accepted["id"])
    service = FinancialService(db_session)
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None

    receivable = api.get(
        f"/api/v1/organizations/{organization_id}/financial/receivables",
        headers=bearer(context["tokens"][0]),
    )
    assert receivable.status_code == 200, receivable.text
    item = receivable.json()["receivables"][0]
    assert item["venue_price_cents"] == 40_000
    assert item["fee_cents"] == 8_000
    assert item["total_cents"] == 48_000
    assert item["receipt_reference"] is None
    assert item["dispute_deadline"] == (
        aware(release.eligible_at) + timedelta(hours=72)
    ).isoformat().replace("+00:00", "Z")

    service.release_due(now=aware(release.eligible_at) + timedelta(minutes=1))
    db_session.commit()

    statement = api.get(
        f"/api/v1/organizations/{organization_id}/financial/statement",
        headers=bearer(context["tokens"][0]),
    )
    assert statement.status_code == 200, statement.text
    entries = statement.json()["entries"]
    confirmed = next(item for item in entries if item["entry_type"] == "PAYMENT_CONFIRMED")
    released = next(item for item in entries if item["entry_type"] == "VENUE_RELEASE")
    for entry in (confirmed, released):
        assert entry["venue_price_cents"] == 40_000
        assert entry["fee_cents"] == 8_000
        assert entry["total_cents"] == 48_000
    assert confirmed["release_id"] is None
    assert released["release_id"] == str(release.id)
    assert released["amount_cents"] == 40_000

    detail = api.get(
        f"/api/v1/organizations/{organization_id}/bookings/{booking_id}/financial",
        headers=bearer(context["tokens"][0]),
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["pricing"] == {
        "venue_price_cents": 40_000,
        "fee_cents": 8_000,
        "fee_percent_applied": 2_000,
        "total_cents": 48_000,
        "pricing_version": "adr0049_v1",
    }
    assert body["release"]["status"] == "RELEASED"
    assert body["release"]["receipt_reference"] == f"simulated:{release.id}"
    assert body["dispute"] is None
    assert body["fiscal_document"] is None
    ledger_release = next(item for item in body["ledger"] if item["entry_type"] == "VENUE_RELEASE")
    assert ledger_release["release_id"] == str(release.id)
    assert ledger_release["venue_price_cents"] == 40_000
    assert ledger_release["fee_cents"] == 8_000
    assert ledger_release["total_cents"] == 48_000


def test_commission_report_keeps_venue_and_joga_fee_separate(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    _, _ = complete_booking(api, context)
    organization_id = context["organization"].id

    response = api.get(
        f"/api/v1/organizations/{organization_id}/financial/commission",
        headers=bearer(context["tokens"][0]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totals"] == {
        "bookings": 1,
        "venue_price_cents": 40_000,
        "joga_fee_cents": 8_000,
        "total_cents": 48_000,
    }
    assert body["rows"][0]["venue_price_cents"] == 40_000
    assert body["rows"][0]["fee_cents"] == 8_000
    # A comissão nunca inclui o valor do fornecedor.
    assert body["totals"]["joga_fee_cents"] != body["totals"]["total_cents"]

    filtered = api.get(
        f"/api/v1/organizations/{organization_id}/financial/commission"
        "?from=2030-01-01T00:00:00%2B00:00",
        headers=bearer(context["tokens"][0]),
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["totals"]["bookings"] == 0
    assert filtered.json()["rows"] == []

    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)
    hidden = api.get(
        f"/api/v1/organizations/{organization_id}/financial/commission",
        headers=bearer(outsider_token),
    )
    assert hidden.status_code == 404


def test_dispute_window_and_released_release_block_contestation(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id
    booking_id = uuid.UUID(accepted["id"])
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None

    release.eligible_at = utcnow() - timedelta(days=2)
    release.dispute_deadline = utcnow() - timedelta(hours=1)
    db_session.commit()
    expired = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
        json={"booking_id": accepted["id"], "reason": "Fora do prazo"},
    )
    assert expired.status_code == 409
    assert expired.json()["detail"]["code"] == "dispute_window_expired"

    release.status = "RELEASED"
    release.released_at = utcnow()
    db_session.commit()
    released = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
        json={"booking_id": accepted["id"], "reason": "Depois do repasse"},
    )
    assert released.status_code == 409
    assert released.json()["detail"]["code"] == "release_not_contestable"


def test_dispute_decision_requires_internal_operator_and_is_audited(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id
    booking_id = uuid.UUID(accepted["id"])

    created = api.post(
        f"/api/v1/organizations/{organization_id}/financial/disputes",
        headers=bearer(context["tokens"][0]),
        json={"booking_id": accepted["id"], "reason": "Valor divergente"},
    )
    assert created.status_code == 201, created.text
    dispute_id = created.json()["id"]
    decision_url = (
        f"/api/v1/organizations/{organization_id}/financial/disputes/{dispute_id}/decision"
    )

    denied = api.post(
        decision_url,
        headers=bearer(context["tokens"][0]),
        json={"decision": "ACCEPTED", "reason": "Autoaprovação"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "operator_not_authorized"

    settings = get_settings().model_copy(update={"review_operators": str(context["users"][0])})
    client.app.dependency_overrides[get_settings] = lambda: settings
    decided = api.post(
        decision_url,
        headers=bearer(context["tokens"][0]),
        json={"decision": "ACCEPTED", "reason": "Contestação procedente"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "ACCEPTED"
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None and release.status == "RELEASED"
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "financial.dispute_decided",
            AuditLog.resource_id == dispute_id,
        )
    )
    assert audit is not None
    assert audit.organization_id == organization_id

    repeated = api.post(
        decision_url,
        headers=bearer(context["tokens"][0]),
        json={"decision": "REJECTED", "reason": "Repetição"},
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "dispute_not_open"

    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)
    hidden = api.post(
        decision_url,
        headers=bearer(outsider_token),
        json={"decision": "ACCEPTED", "reason": "Outra organização"},
    )
    assert hidden.status_code == 404

    assert reconcile(db_session) == []


def test_chargeback_block_prevents_release_without_touching_balance(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    booking_id = uuid.UUID(accepted["id"])
    service = FinancialService(db_session)
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    assert release is not None

    blocked = service.block_for_chargeback(booking_id, reason="MED aberto")
    db_session.commit()
    assert blocked is not None
    assert blocked.status == "FAILED"
    assert blocked.failed_at is not None
    assert blocked.reason == "MED aberto"
    assert service.release_due(now=aware(release.eligible_at) + timedelta(days=1)) == 0

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "financial.release_blocked")
    )
    assert audit is not None

    assert service.block_for_chargeback(booking_id, reason="Repetição") is not None
    db_session.commit()
    assert db_session.get(VenueRelease, release.id).status == "FAILED"


def test_booking_financial_shows_fiscal_placeholder(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id
    booking_id = uuid.UUID(accepted["id"])
    db_session.add(
        FiscalDocument(
            booking_id=booking_id,
            issuer_cnpj="12345678000199",
            taker_user_id=context["users"][0],
            amount_cents=40_000,
            status="pending_manual",
        )
    )
    db_session.commit()

    detail = api.get(
        f"/api/v1/organizations/{organization_id}/bookings/{booking_id}/financial",
        headers=bearer(context["tokens"][0]),
    )
    assert detail.status_code == 200, detail.text
    document = detail.json()["fiscal_document"]
    assert document["status"] == "pending_manual"
    assert document["amount_cents"] == 40_000
    assert document["number"] is None
    assert document["issued_at"] is None


def test_statement_projection_matches_venue_ledger(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted, _ = complete_booking(api, context)
    organization_id = context["organization"].id
    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(accepted["id"]))
    )
    assert release is not None
    FinancialService(db_session).release_due(now=aware(release.eligible_at) + timedelta(minutes=1))
    db_session.commit()

    statement = api.get(
        f"/api/v1/organizations/{organization_id}/financial/statement",
        headers=bearer(context["tokens"][0]),
    )
    assert statement.status_code == 200, statement.text
    entries = statement.json()["entries"]
    assert entries

    for entry in entries:
        ledger_total = db_session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0))
            .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
            .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
            .where(
                LedgerTransaction.id == uuid.UUID(entry["id"]),
                LedgerAccount.owner_kind == "venue",
            )
        )
        assert entry["amount_cents"] == int(ledger_total or 0)
