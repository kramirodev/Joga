"""Contrato OpenAPI da interface financeira (Fase 15 sobre o ledger em reais)."""

from __future__ import annotations

from app.main import create_app


def test_openapi_exposes_financial_contract() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    assert "/api/v1/organizations/{organization_id}/financial/commission" in paths
    assert (
        "/api/v1/organizations/{organization_id}/financial/disputes/{dispute_id}/decision" in paths
    )

    schemas = schema["components"]["schemas"]
    receivable = set(schemas["ReceivableView"]["properties"])
    assert {
        "venue_price_cents",
        "fee_cents",
        "total_cents",
        "receipt_reference",
        "dispute_deadline",
        "reason",
    } <= receivable

    statement = set(schemas["StatementEntryView"]["properties"])
    assert {"release_id", "venue_price_cents", "fee_cents", "total_cents"} <= statement

    ledger = set(schemas["LedgerView"]["properties"])
    assert {"release_id", "venue_price_cents", "fee_cents", "total_cents"} <= ledger

    booking = set(schemas["BookingFinancialResponse"]["properties"])
    assert {"pricing", "release", "dispute", "fiscal_document"} <= booking

    summary = set(schemas["OrganizationSummaryResponse"]["properties"])
    assert {"venue_price_cents", "joga_fee_cents", "reversed_cents", "failed_cents"} <= summary

    commission = schemas["CommissionResponse"]["properties"]
    assert {"rows", "totals"} <= set(commission)
