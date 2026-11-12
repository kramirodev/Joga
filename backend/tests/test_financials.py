"""Testes da interface financeira, liberações e conciliação (Fase 15)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking
from app.modules.organizations.models import OrganizationMembership
from app.modules.organizations.permissions import Role
from app.modules.payments.financial import (
    DisputeConflict,
    DisputeStateError,
    FinancialService,
    OperatorNotAuthorized,
)
from app.modules.payments.models import FinancialDispute, LedgerEntry, VenueRelease
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
        .select_from(LedgerEntry)
        .where(
            LedgerEntry.booking_id == booking_id,
            LedgerEntry.entry_type == "VENUE_RELEASE",
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
    entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.booking_id == booking_id,
            LedgerEntry.entry_type == "VENUE_RELEASE",
        )
    ).all()
    assert len(entries) == 1
    assert entries[0].amount_cents == 40_000

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
    service = FinancialService(db_session)
    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(accepted["id"]))
    )
    assert release is not None
    service.release_due(now=aware(release.eligible_at) + timedelta(minutes=1))
    db_session.commit()

    statement = api.get(
        f"/api/v1/organizations/{organization_id}/financial/statement",
        headers=bearer(context["tokens"][0]),
    )
    assert statement.status_code == 200, statement.text
    types = [entry["entry_type"] for entry in statement.json()["entries"]]
    assert "CHARGE_CREATED" in types
    assert "PAYMENT_CONFIRMED" in types
    assert "VENUE_RELEASE" in types

    entry = db_session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.booking_id == uuid.UUID(accepted["id"]),
            LedgerEntry.entry_type == "VENUE_RELEASE",
        )
    )
    assert entry is not None
    db_session.delete(entry)
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
