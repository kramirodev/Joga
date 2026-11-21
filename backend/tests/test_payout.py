"""Testes de fornecedor e chave de repasse (Fase 14D.2)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.cnpj_helpers import (
    PARTNER_CPF,
    FakeCnpjLookup,
    api_with_lookup,
    make_cnpj_user,
    next_partner_cpf,
)
from tests.helpers_results import make_token

VALID_CNPJ = "11222333000181"


def api_client(client: TestClient, db_session: Session) -> TestClient:
    return api_with_lookup(client, db_session, FakeCnpjLookup())


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_org(api: TestClient, token: str) -> str:
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json={"name": "Arena Pix", "cnpj": VALID_CNPJ, "cpf": PARTNER_CPF},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_payout(api: TestClient, token: str, org_id: str, **overrides: str) -> dict:
    payload = {
        "legal_document": VALID_CNPJ,
        "pix_key_type": "email",
        "pix_key": "financeiro@arena.com",
        **overrides,
    }
    response = api.put(
        f"/api/v1/organizations/{org_id}/payout", headers=bearer(token), json=payload
    )
    return {"status": response.status_code, "body": response.json()}


def test_valid_payout_marks_organization_ready(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    org_id = create_org(api, token)

    result = set_payout(api, token, org_id)
    assert result["status"] == 200, result["body"]
    body = result["body"]
    assert body["payout_ready"] is True
    assert body["payout_status"] == "active"
    assert body["pix_key_type"] == "email"
    assert body["pix_key_masked"] == "f***@arena.com"
    assert "financeiro" not in str(body)


def test_formatted_cnpj_is_accepted(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    org_id = create_org(api, token)

    result = set_payout(api, token, org_id, legal_document="11.222.333/0001-81")
    assert result["status"] == 200, result["body"]


def test_invalid_cnpj_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    org_id = create_org(api, token)

    result = set_payout(api, token, org_id, legal_document="11222333000180")
    assert result["status"] == 422, result["body"]
    assert result["body"]["detail"]["code"] == "invalid_input"


def test_invalid_email_key_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    org_id = create_org(api, token)

    result = set_payout(api, token, org_id, pix_key="nao-e-email")
    assert result["status"] == 422, result["body"]


def test_operator_cannot_set_payout(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_cnpj_user(db_session)
    owner_token = make_token(db_session, owner_id)
    org_id = create_org(api, owner_token)

    operator_id = make_cnpj_user(db_session, cpf=next_partner_cpf())
    operator_token = make_token(db_session, operator_id)
    added = api.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=bearer(owner_token),
        json={"user_id": str(operator_id), "role": "OPERATOR"},
    )
    assert added.status_code == 201, added.text

    result = set_payout(api, operator_token, org_id)
    assert result["status"] == 403, result["body"]
    assert result["body"]["detail"]["code"] == "forbidden"


def test_organization_starts_without_payout(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    org_id = create_org(api, token)

    response = api.get(f"/api/v1/organizations/{org_id}", headers=bearer(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["payout_ready"] is False
    assert body["payout_status"] == "pending"
    assert body["pix_key_masked"] is None
