"""Testes da Etapa 8 (14E-E): CPF, fiscal, termos e reembolso parcial."""

from __future__ import annotations

import base64
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.fiscal.models import FiscalDocument, FiscalDocumentTaker
from app.modules.fiscal.service import TakerSnapshot, record_document_intent
from app.modules.identity.models import AuditLog
from app.modules.legal import service as legal_service
from app.modules.legal.models import TermsAcceptance
from app.modules.payments.models import PaymentRefund
from app.modules.profile.cpf import (
    CpfDecryptionError,
    CpfKeyUnavailable,
    InvalidCpf,
    decrypt_cpf,
    encrypt_cpf,
    mask_cpf,
    normalize_cpf,
)
from app.modules.profile.models import UserProfile
from app.modules.tickets.models import TicketPurchase
from tests.compliance_helpers import (
    TEST_CPF,
    TEST_CPF_KEY,
    TEST_CPF_KEY_ID,
    cpf_key_kwargs,
)
from tests.helpers_results import make_token, make_user
from tests.test_ticket_settlement import bearer, open_booking, setup_context

OTHER_CPF = "11144477735"


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_cpf_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **cpf_key_kwargs(), **overrides)


def cpf_settings() -> Settings:
    """Dependência sem argumentos para o override do FastAPI."""
    return make_cpf_settings()


def test_cpf_roundtrip_is_bound_to_user() -> None:
    settings = cpf_settings()
    user_id = uuid.uuid4()
    other_id = uuid.uuid4()

    ciphertext, key_id, last2 = encrypt_cpf(TEST_CPF, user_id, settings)

    assert TEST_CPF.encode("ascii") not in ciphertext
    assert key_id == TEST_CPF_KEY_ID
    assert last2 == TEST_CPF[-2:]
    assert decrypt_cpf(ciphertext, user_id, key_id, settings) == TEST_CPF
    with pytest.raises(CpfDecryptionError):
        decrypt_cpf(ciphertext, other_id, key_id, settings)


def test_cpf_tampered_ciphertext_does_not_decrypt() -> None:
    settings = cpf_settings()
    user_id = uuid.uuid4()
    ciphertext, key_id, _ = encrypt_cpf(TEST_CPF, user_id, settings)
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0xFF])

    with pytest.raises(CpfDecryptionError):
        decrypt_cpf(tampered, user_id, key_id, settings)


def test_cpf_rotation_reads_previous_key() -> None:
    old_key = base64.b64encode(b"o" * 32).decode("ascii")
    new_key = base64.b64encode(b"n" * 32).decode("ascii")
    old_settings = Settings(
        _env_file=None,
        cpf_key=SecretStr(old_key),
        cpf_key_id="old-v1",
    )
    user_id = uuid.uuid4()
    ciphertext, key_id, _ = encrypt_cpf(TEST_CPF, user_id, old_settings)

    rotated = Settings(
        _env_file=None,
        cpf_key=SecretStr(new_key),
        cpf_key_id="new-v1",
        cpf_previous_keys={"old-v1": SecretStr(old_key)},
    )
    assert decrypt_cpf(ciphertext, user_id, key_id, rotated) == TEST_CPF
    with pytest.raises(CpfKeyUnavailable):
        encrypt_cpf(TEST_CPF, user_id, Settings(_env_file=None, cpf_key=None, cpf_key_id=None))


@pytest.mark.parametrize(
    "value",
    ["", "123", "11111111111", "52998224724", "529.982.247-2x"],
)
def test_cpf_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidCpf):
        normalize_cpf(value)


def test_cpf_accepts_formatting_and_masks() -> None:
    assert normalize_cpf("529.982.247-25") == TEST_CPF
    assert normalize_cpf("111.444.777-35") == OTHER_CPF
    assert mask_cpf(TEST_CPF[-2:]) == "***.***.***-25"
    assert mask_cpf(None) is None


def test_cpf_key_is_required_outside_local_and_rejects_placeholder() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            cpf_key=None,
            cpf_key_id=None,
            web_cookie_secure=True,
        )

    zero_key = base64.b64encode(b"\x00" * 32).decode("ascii")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            cpf_key=SecretStr(zero_key),
            cpf_key_id="zero",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            cpf_key=SecretStr(base64.b64encode(b"short").decode("ascii")),
            cpf_key_id="short",
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cpf_key=SecretStr(TEST_CPF_KEY), cpf_key_id=None)


def test_cpf_api_returns_only_mask_and_isolates_users(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    client.app.dependency_overrides[get_settings] = cpf_settings
    user_id = make_user(db_session)
    other_id = make_user(db_session)
    token = make_token(db_session, user_id)
    other_token = make_token(db_session, other_id)

    saved = api.put("/api/v1/me/cpf", headers=bearer(token), json={"cpf": TEST_CPF})
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"cpf_present": True, "cpf_masked": "***.***.***-25"}
    assert TEST_CPF not in saved.text

    read = api.get("/api/v1/me/cpf", headers=bearer(token))
    assert read.status_code == 200
    assert read.json()["cpf_masked"] == "***.***.***-25"
    assert TEST_CPF not in read.text

    other = api.get("/api/v1/me/cpf", headers=bearer(other_token))
    assert other.status_code == 200
    assert other.json() == {"cpf_present": False, "cpf_masked": None}

    profile = db_session.get(UserProfile, user_id)
    assert profile is not None
    assert profile.cpf_ciphertext is not None
    assert TEST_CPF.encode("ascii") not in profile.cpf_ciphertext
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.actor_user_id == user_id,
            AuditLog.action == "user.cpf_updated",
        )
    )
    assert audit is not None
    assert TEST_CPF not in str(audit.details)

    removed = api.delete("/api/v1/me/cpf", headers=bearer(token))
    assert removed.status_code == 200
    assert removed.json() == {"cpf_present": False, "cpf_masked": None}
    db_session.refresh(profile)
    assert profile.cpf_ciphertext is None


def test_cpf_api_rejects_invalid_without_echoing(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    client.app.dependency_overrides[get_settings] = cpf_settings
    token = make_token(db_session, make_user(db_session))

    response = api.put(
        "/api/v1/me/cpf",
        headers=bearer(token),
        json={"cpf": "111.111.111-11"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_cpf"}}
    assert "11111111111" not in response.text


def test_fiscal_intent_records_one_taker_per_player(db_session: Session) -> None:
    settings = make_cpf_settings(fiscal_mode="placeholder")
    booking_id = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    ciphertext, key_id, _ = encrypt_cpf(TEST_CPF, first, settings)

    document = record_document_intent(
        db_session,
        booking_id=booking_id,
        issuer_cnpj="12.345.678/0001-90",
        taker_user_id=first,
        amount_cents=15000,
        takers=[
            TakerSnapshot(first, 7500, ciphertext, key_id),
            TakerSnapshot(second, 7500),
        ],
        settings=settings,
    )
    assert document is not None
    assert document.status == "pending_manual"
    assert document.amount_cents == 15000

    takers = list(
        db_session.scalars(
            select(FiscalDocumentTaker).where(FiscalDocumentTaker.fiscal_document_id == document.id)
        )
    )
    assert {taker.user_id for taker in takers} == {first, second}
    assert sum(taker.amount_cents for taker in takers) == 15000
    stored = next(taker for taker in takers if taker.user_id == first)
    assert stored.cpf_ciphertext == ciphertext
    assert decrypt_cpf(stored.cpf_ciphertext, first, stored.cpf_key_id, settings) == TEST_CPF

    again = record_document_intent(
        db_session,
        booking_id=booking_id,
        issuer_cnpj="12345678000190",
        taker_user_id=first,
        amount_cents=99900,
        takers=[TakerSnapshot(first, 7500), TakerSnapshot(second, 7500)],
        settings=settings,
    )
    assert again is not None
    assert again.id == document.id
    assert db_session.query(FiscalDocument).count() == 1
    assert db_session.query(FiscalDocumentTaker).count() == 2


def test_booking_confirmation_creates_fiscal_intent(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = api_client(client, db_session)
    settings = make_cpf_settings(fiscal_mode="placeholder")
    monkeypatch.setattr("app.modules.bookings.service.get_settings", lambda: settings)
    context = setup_context(db_session)
    first_user = context["users"][0]
    ciphertext, key_id, last2 = encrypt_cpf(TEST_CPF, first_user, settings)
    db_session.add(
        UserProfile(
            user_id=first_user,
            cpf_ciphertext=ciphertext,
            cpf_key_id=key_id,
            cpf_last2=last2,
        )
    )
    db_session.flush()

    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    booking_id = uuid.UUID(booking["id"])
    document = db_session.scalar(
        select(FiscalDocument).where(FiscalDocument.booking_id == booking_id)
    )
    assert document is not None
    assert document.status == "pending_manual"
    assert document.issuer_cnpj == context["organization"].legal_document
    assert document.provider_ref is None
    stored_booking = db_session.get(Booking, booking_id)
    assert stored_booking is not None
    assert document.amount_cents == stored_booking.venue_price_cents

    takers = list(
        db_session.scalars(
            select(FiscalDocumentTaker).where(FiscalDocumentTaker.fiscal_document_id == document.id)
        )
    )
    assert len(takers) == len(context["users"])
    assert sum(taker.amount_cents for taker in takers) == stored_booking.venue_price_cents
    first_taker = next(taker for taker in takers if taker.user_id == first_user)
    assert first_taker.cpf_ciphertext == ciphertext


def test_terms_draft_cannot_be_accepted_and_approved_is_idempotent(
    db_session: Session,
) -> None:
    draft = legal_service.create_draft(db_session, version="2026-11")
    with pytest.raises(legal_service.TermsNotApproved):
        legal_service.accept_terms(
            db_session,
            user_id=uuid.uuid4(),
            terms_version_id=draft.id,
            context="credit_purchase",
            ip_hash="a" * 64,
        )

    legal_service.approve(db_session, draft, legal_review_ref="OAB-2026-11")
    user_id = uuid.uuid4()
    first = legal_service.accept_terms(
        db_session,
        user_id=user_id,
        terms_version_id=draft.id,
        context="credit_purchase",
        ip_hash="a" * 64,
        user_agent_hash="b" * 64,
    )
    second = legal_service.accept_terms(
        db_session,
        user_id=user_id,
        terms_version_id=draft.id,
        context="credit_purchase",
        ip_hash="c" * 64,
    )
    assert second.id == first.id
    assert first.terms_hash == legal_service.content_hash(draft)
    assert db_session.query(TermsAcceptance).count() == 1


def test_terms_api_only_exposes_approved_version(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    draft = legal_service.create_draft(db_session, version="2026-11")
    db_session.commit()

    current = api.get("/api/v1/legal/terms/current")
    assert current.status_code == 200
    assert current.json() == {"terms": None}

    rejected = api.post(
        "/api/v1/legal/terms/accept",
        headers=bearer(token),
        json={"terms_version_id": str(draft.id), "context": "credit_purchase"},
    )
    assert rejected.status_code == 409
    assert rejected.json() == {"detail": {"code": "terms_not_approved"}}

    legal_service.approve(db_session, draft, legal_review_ref="OAB-2026-11")
    db_session.commit()

    current = api.get("/api/v1/legal/terms/current")
    assert current.status_code == 200
    body = current.json()["terms"]
    assert body["id"] == str(draft.id)
    assert body["version"] == "2026-11"
    assert body["terms_hash"] == legal_service.content_hash(draft)
    assert body["published_at"]

    accepted = api.post(
        "/api/v1/legal/terms/accept",
        headers=bearer(token),
        json={"terms_version_id": str(draft.id), "context": "credit_purchase"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["terms_hash"] == legal_service.content_hash(draft)
    replay = api.post(
        "/api/v1/legal/terms/accept",
        headers=bearer(token),
        json={"terms_version_id": str(draft.id), "context": "credit_purchase"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == accepted.json()["id"]


def test_purchase_requires_acceptance_when_terms_are_approved(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    client.app.dependency_overrides[get_settings] = cpf_settings
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    terms = legal_service.create_draft(db_session, version="2026-11")
    legal_service.approve(db_session, terms, legal_review_ref="OAB-2026-11")
    db_session.commit()

    missing = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert missing.status_code == 422
    assert missing.json() == {"detail": {"code": "terms_not_accepted"}}
    assert db_session.scalar(select(TicketPurchase.id)) is None

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso", "terms_version_id": str(terms.id)},
    )
    assert created.status_code == 201, created.text
    acceptance = db_session.scalar(
        select(TermsAcceptance).where(
            TermsAcceptance.user_id == user_id,
            TermsAcceptance.context == "credit_purchase",
        )
    )
    assert acceptance is not None
    assert acceptance.terms_version_id == terms.id


def test_purchase_without_approved_terms_keeps_current_behavior(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert created.status_code == 201, created.text
    assert db_session.query(TermsAcceptance).count() == 0


def test_payment_refund_schema_allows_partial_but_one_full(db_session: Session) -> None:
    payment_id = uuid.uuid4()
    partials = [
        PaymentRefund(
            booking_id=uuid.uuid4(),
            booking_payment_id=payment_id,
            amount_cents=500,
            refund_type="PARTIAL",
            idempotency_key=f"refund:{payment_id}:part:{index}",
        )
        for index in range(2)
    ]
    db_session.add_all(partials)
    db_session.flush()

    db_session.add(
        PaymentRefund(
            booking_id=uuid.uuid4(),
            booking_payment_id=payment_id,
            amount_cents=1000,
            refund_type="FULL",
            idempotency_key=f"refund:{payment_id}:full",
        )
    )
    db_session.flush()

    db_session.add(
        PaymentRefund(
            booking_id=uuid.uuid4(),
            booking_payment_id=payment_id,
            amount_cents=1000,
            refund_type="FULL",
            idempotency_key=f"refund:{payment_id}:full-duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
