"""Testes dos placeholders de fiscal, termos e modos financeiros (ADR 0049 §5)."""

import uuid
from collections.abc import Callable

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.fiscal.models import FiscalDocument
from app.modules.fiscal.service import (
    mark_failed,
    mark_issued,
    normalize_cnpj,
    record_document_intent,
)
from app.modules.legal import service as legal_service


@pytest.fixture
def document_factory(db_session: Session) -> Callable[[], FiscalDocument]:
    settings = Settings(_env_file=None, fiscal_mode="placeholder")

    def make() -> FiscalDocument:
        document = record_document_intent(
            db_session,
            booking_id=uuid.uuid4(),
            issuer_cnpj="12345678000190",
            taker_user_id=uuid.uuid4(),
            amount_cents=15000,
            settings=settings,
        )
        assert document is not None
        return document

    return make


def test_defaults_keep_every_placeholder_off() -> None:
    settings = Settings(_env_file=None)

    assert settings.money_mode == "simulated"
    assert settings.legal_approval_ref is None
    assert settings.fiscal_mode == "disabled"
    assert settings.custody_model == "B"
    assert settings.tax_rate_bps == 1550
    assert settings.fee_percent_bps == 2000
    assert settings.fee_min_cents == 800


def test_real_money_requires_legal_reference() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, money_mode="real")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, money_mode="real", legal_approval_ref="   ")

    reference = {
        "legal_approval_ref": "parecer-fiscal-juridico-2026-11",
        "legal_approval_sha256": "a" * 64,
        "legal_approval_date": "2026-11-15",
    }
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, money_mode="real", legal_approval_ref=reference["legal_approval_ref"]
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            money_mode="real",
            legal_approval_ref=reference["legal_approval_ref"],
            legal_approval_sha256=reference["legal_approval_sha256"],
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            money_mode="real",
            legal_approval_ref=reference["legal_approval_ref"],
            legal_approval_sha256=reference["legal_approval_sha256"],
            legal_approval_date="2999-01-01",
        )

    settings = Settings(_env_file=None, money_mode="real", **reference)
    assert settings.money_mode == "real"


def test_custody_model_c_fails_at_startup() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, custody_model="C")


def test_fiscal_provider_fails_at_startup() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, fiscal_mode="provider")


def test_disabled_fiscal_mode_records_nothing(db_session: Session) -> None:
    settings = Settings(_env_file=None, fiscal_mode="disabled")

    document = record_document_intent(
        db_session,
        booking_id=uuid.uuid4(),
        issuer_cnpj="12.345.678/0001-90",
        taker_user_id=uuid.uuid4(),
        amount_cents=15000,
        settings=settings,
    )

    assert document is None
    assert db_session.query(FiscalDocument).count() == 0


def test_placeholder_records_pending_manual_without_provider(db_session: Session) -> None:
    settings = Settings(_env_file=None, fiscal_mode="placeholder")
    booking_id = uuid.uuid4()

    document = record_document_intent(
        db_session,
        booking_id=booking_id,
        issuer_cnpj="12.345.678/0001-90",
        taker_user_id=uuid.uuid4(),
        amount_cents=15000,
        settings=settings,
    )

    assert document is not None
    assert document.status == "pending_manual"
    assert document.issuer_cnpj == "12345678000190"
    assert document.number is None
    assert document.provider_ref is None

    again = record_document_intent(
        db_session,
        booking_id=booking_id,
        issuer_cnpj="12345678000190",
        taker_user_id=uuid.uuid4(),
        amount_cents=99900,
        settings=settings,
    )
    assert again is not None
    assert again.id == document.id
    assert again.amount_cents == 15000
    assert db_session.query(FiscalDocument).count() == 1


def test_record_rejects_negative_amount(db_session: Session) -> None:
    settings = Settings(_env_file=None, fiscal_mode="placeholder")

    with pytest.raises(ValueError):
        record_document_intent(
            db_session,
            booking_id=uuid.uuid4(),
            issuer_cnpj="12345678000190",
            taker_user_id=uuid.uuid4(),
            amount_cents=-1,
            settings=settings,
        )


def test_normalize_cnpj_requires_fourteen_digits() -> None:
    assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"
    with pytest.raises(ValueError):
        normalize_cnpj("123")


def test_mark_issued_and_failed(document_factory, db_session: Session) -> None:
    document = document_factory()

    mark_issued(db_session, document, number=" 42 ", issued_at=None)
    assert document.status == "issued"
    assert document.number == "42"
    assert document.issued_at is not None

    with pytest.raises(ValueError):
        mark_issued(db_session, document, number="  ")

    mark_failed(db_session, document)
    assert document.status == "failed"


def test_terms_draft_cannot_be_accepted(db_session: Session) -> None:
    terms = legal_service.create_draft(db_session, version="2026-11")

    assert terms.status == "draft"
    assert terms.published_at is None
    with pytest.raises(ValueError):
        legal_service.assert_acceptable(terms)
    assert legal_service.latest_approved(db_session) is None


def test_terms_approval_requires_reference_and_is_immutable(db_session: Session) -> None:
    terms = legal_service.create_draft(db_session, version="2026-11")

    with pytest.raises(ValueError):
        legal_service.approve(db_session, terms, legal_review_ref="  ")

    legal_service.approve(db_session, terms, legal_review_ref="OAB-2026-11")
    assert terms.status == "approved"
    assert terms.published_at is not None
    legal_service.assert_acceptable(terms)
    assert legal_service.latest_approved(db_session) is terms

    with pytest.raises(ValueError):
        legal_service.approve(db_session, terms, legal_review_ref="OAB-2026-12")


def test_terms_version_is_unique(db_session: Session) -> None:
    legal_service.create_draft(db_session, version="2026-11")

    with pytest.raises(ValueError):
        legal_service.create_draft(db_session, version="2026-11")
