"""Verificação automática de CNPJ da organização (ADR 0062)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import AuditLog
from app.modules.organizations.cnpj import (
    BrasilApiCnpjLookup,
    CnpjNotFound,
    CnpjProviderUnavailable,
    InvalidCnpj,
    QsaPartner,
    address_matches,
    cpf_masked_matches,
    mask_cnpj,
    names_match,
    normalize_cnpj,
)
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.organizations.verification import OrganizationVerificationService
from app.modules.profile.models import UserProfile
from tests.cnpj_helpers import (
    PARTNER_CPF,
    PARTNER_CPF_MASKED,
    PARTNER_NAME,
    FakeCnpjLookup,
    api_with_lookup,
    attach_partner_profile,
    cnpj_record,
    make_cnpj_user,
)
from tests.helpers_results import make_token, make_user


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_org_payload(cnpj: str = "11222333000181", cpf: str = PARTNER_CPF) -> dict:
    return {"name": "Arena Verificada", "cnpj": cnpj, "cpf": cpf}


def login_with_partner(db_session: Session, **profile: str) -> tuple[uuid.UUID, str]:
    user_id = make_cnpj_user(db_session, **profile)
    token = make_token(db_session, user_id)
    return user_id, token


def create_verified_org(
    api: TestClient,
    token: str,
    *,
    cnpj: str = "11222333000181",
) -> dict:
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(cnpj=cnpj),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _non_platform_organizations(db_session: Session) -> list[Organization]:
    return list(
        db_session.scalars(select(Organization).where(Organization.is_platform.is_(False))).all()
    )


def audit_details(db_session: Session, action: str) -> list[dict]:
    events = db_session.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)
    ).all()
    return [event.details or {} for event in events]


def test_creates_verified_organization_and_persists_masked_snapshot(
    client: TestClient,
    db_session: Session,
) -> None:
    lookup = FakeCnpjLookup()
    api = api_with_lookup(client, db_session, lookup)
    user_id, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(cnpj="11.222.333/0001-81", cpf="111.444.777-35"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cnpj"] == "11222333000181"
    assert body["cnpj_status"] == "ATIVA"
    assert body["verification_status"] == "verified"
    assert body["cnpj_verified_at"] is not None
    assert body["cnpj_next_check_at"] is not None
    verified_at = datetime.fromisoformat(body["cnpj_verified_at"])
    next_check = datetime.fromisoformat(body["cnpj_next_check_at"])
    assert next_check - verified_at == timedelta(days=7)
    assert "cpf" not in body
    assert PARTNER_CPF not in response.text

    organization = db_session.get(Organization, uuid.UUID(body["id"]))
    assert organization is not None
    assert organization.cnpj == "11222333000181"
    snapshot = organization.cnpj_snapshot or {}
    assert snapshot["qsa"][0]["cpf_masked"] == PARTNER_CPF_MASKED
    assert PARTNER_CPF not in str(snapshot)

    profile = db_session.get(UserProfile, user_id)
    assert profile is not None
    assert profile.cpf_ciphertext is not None
    assert PARTNER_CPF not in str(profile.cpf_ciphertext)

    created = audit_details(db_session, "organization.created")
    verified = audit_details(db_session, "organization.cnpj_verified")
    assert created[0]["verification_status"] == "verified"
    assert verified[0]["result"] == "verified"
    assert verified[0]["cnae_matched"] == "9311500"
    assert PARTNER_CPF not in str(verified)
    assert lookup.calls == ["11222333000181"]

    venue = api.post(
        f"/api/v1/organizations/{body['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Quadra Central",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "postal_code": "20541-004",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text
    assert venue.json()["postal_code"] == "20541004"


def test_rejects_active_cnpj_with_incompatible_cnae(
    client: TestClient,
    db_session: Session,
) -> None:
    lookup = FakeCnpjLookup(
        cnpj_record(
            cnae_fiscal="9430800",
            cnae_descricao="Atividades de associações",
            secondary_cnaes=(),
        )
    )
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_cnae_incompatible"}}
    assert not _non_platform_organizations(db_session)
    rejected = audit_details(db_session, "organization.cnpj_rejected")
    assert rejected[0]["reason"] == "cnae_incompatible"
    assert PARTNER_CPF not in str(rejected)


def test_rejects_cnpj_not_active(client: TestClient, db_session: Session) -> None:
    lookup = FakeCnpjLookup(
        cnpj_record(situacao_cadastral="BAIXADA", data_situacao_cadastral="2024-01-01")
    )
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_inactive"}}
    assert not _non_platform_organizations(db_session)


def test_rejects_venue_outside_cnpj_municipality(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization = create_verified_org(api, token)

    response = api.post(
        f"/api/v1/organizations/{organization['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Quadra Paulista",
            "city": "São Paulo",
            "state": "SP",
            "latitude": -23.55,
            "longitude": -46.63,
        },
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_address_mismatch"}}
    assert db_session.scalar(select(OrganizationVenue)) is None


def test_rejects_owner_cpf_outside_qsa(client: TestClient, db_session: Session) -> None:
    lookup = FakeCnpjLookup(
        cnpj_record(
            qsa=(
                QsaPartner(
                    nome="OUTRA PESSOA",
                    cpf_masked="***999999**",
                    qualificacao="Sócio",
                ),
            )
        )
    )
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_owner_mismatch"}}
    assert not _non_platform_organizations(db_session)


def test_rejects_responsible_name_not_in_qsa(client: TestClient, db_session: Session) -> None:
    lookup = FakeCnpjLookup(
        cnpj_record(
            qsa=(
                QsaPartner(
                    nome="OUTRA PESSOA",
                    cpf_masked=PARTNER_CPF_MASKED,
                    qualificacao="Sócio",
                ),
            )
        )
    )
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session, display_name=PARTNER_NAME)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_owner_mismatch"}}


def test_rejects_cpf_divergent_from_stored_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    user_id = make_user(db_session)
    attach_partner_profile(db_session, user_id, cpf="52998224725")
    token = make_token(db_session, user_id)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(cpf=PARTNER_CPF),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_owner_mismatch"}}


def test_rejects_missing_responsible_name(client: TestClient, db_session: Session) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_owner_mismatch"}}


def test_lookup_unavailable_fails_closed(client: TestClient, db_session: Session) -> None:
    lookup = FakeCnpjLookup(error=CnpjProviderUnavailable("indisponível"))
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_lookup_unavailable"}}
    assert not _non_platform_organizations(db_session)


def test_invalid_cnpj_digits_never_reach_provider(
    client: TestClient,
    db_session: Session,
) -> None:
    lookup = FakeCnpjLookup()
    api = api_with_lookup(client, db_session, lookup)
    _, token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(cnpj="11222333000180"),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "cnpj_invalid"}}
    assert lookup.calls == []


def test_duplicate_cnpj_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, first_token = login_with_partner(db_session)
    create_verified_org(api, first_token)
    _, second_token = login_with_partner(db_session)

    response = api.post(
        "/api/v1/organizations",
        headers=bearer(second_token),
        json=create_org_payload(),
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "cnpj_already_registered"}}


def test_payout_cnpj_must_match_verified_cnpj(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization = create_verified_org(api, token)

    response = api.put(
        f"/api/v1/organizations/{organization['id']}/payout",
        headers=bearer(token),
        json={
            "legal_document": "22333444000181",
            "pix_key_type": "email",
            "pix_key": "financeiro@arena.test",
        },
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_input"}}


def test_pending_legacy_organization_can_submit_verification(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    organization = Organization(name="Arena Legada", verification_status="pending")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user_id,
            role=Role.OWNER.value,
        )
    )
    db_session.flush()

    response = api.post(
        f"/api/v1/organizations/{organization.id}/verification",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["verification_status"] == "verified"
    assert response.json()["cnpj"] == "11222333000181"

    venue = api.post(
        f"/api/v1/organizations/{organization.id}/venues",
        headers=bearer(token),
        json={
            "name": "Quadra Regularizada",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text


def test_verified_organization_cannot_change_cnpj(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization = create_verified_org(api, token)

    response = api.post(
        f"/api/v1/organizations/{organization['id']}/verification",
        headers=bearer(token),
        json=create_org_payload(cnpj="22333444000181"),
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "cnpj_change_not_allowed"}}


def test_pending_organization_cannot_create_or_publish_venue(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    organization = Organization(name="Arena Pendente", verification_status="pending")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user_id,
            role=Role.OWNER.value,
        )
    )
    db_session.flush()

    response = api.post(
        f"/api/v1/organizations/{organization.id}/venues",
        headers=bearer(token),
        json={
            "name": "Quadra Pendente",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "organization_not_verified"}}


def test_recheck_in_7_days_marks_inactive_and_unpublishes(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization_body = create_verified_org(api, token)
    venue = api.post(
        f"/api/v1/organizations/{organization_body['id']}/venues",
        headers=bearer(token),
        json={
            "name": "Quadra Central",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text
    venue_model = db_session.get(OrganizationVenue, uuid.UUID(venue.json()["id"]))
    assert venue_model is not None
    venue_model.is_public = True
    db_session.flush()

    organization = db_session.get(Organization, uuid.UUID(organization_body["id"]))
    assert organization is not None
    assert organization.cnpj_next_check_at is not None
    organization.cnpj_next_check_at = utcnow() - timedelta(minutes=1)
    db_session.flush()

    lookup = FakeCnpjLookup(
        cnpj_record(situacao_cadastral="BAIXADA", data_situacao_cadastral="2026-11-21")
    )
    report = OrganizationVerificationService(db_session, get_settings(), lookup).recheck_due(
        limit=10
    )
    db_session.flush()
    assert report.checked == 1
    assert report.invalid == 1
    assert report.unavailable == 0

    db_session.refresh(organization)
    assert organization.verification_status == "invalid"
    assert organization.cnpj_status == "BAIXADA"
    db_session.refresh(venue_model)
    assert venue_model.status == "inactive"
    assert venue_model.is_public is False

    failed = audit_details(db_session, "organization.cnpj_recheck_failed")
    assert failed[0]["reason"] == "inactive"
    assert failed[0]["venues_unpublished"] == 1


def test_recheck_skips_organizations_not_due(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    create_verified_org(api, token)
    db_session.flush()

    report = OrganizationVerificationService(
        db_session, get_settings(), FakeCnpjLookup()
    ).recheck_due(limit=10)
    assert report.checked == 0


def test_recheck_unavailable_keeps_verified_and_retries(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization_body = create_verified_org(api, token)

    organization = db_session.get(Organization, uuid.UUID(organization_body["id"]))
    assert organization is not None
    organization.cnpj_next_check_at = utcnow() - timedelta(minutes=1)
    db_session.flush()

    lookup = FakeCnpjLookup(error=CnpjProviderUnavailable("indisponível"))
    report = OrganizationVerificationService(db_session, get_settings(), lookup).recheck_due(
        limit=10
    )
    db_session.flush()
    assert report.checked == 1
    assert report.unavailable == 1

    db_session.refresh(organization)
    assert organization.verification_status == "verified"
    assert organization.cnpj_next_check_at is not None
    assert ensure_utc(organization.cnpj_next_check_at) > utcnow() + timedelta(hours=1)
    unavailable = audit_details(db_session, "organization.cnpj_recheck_unavailable")
    assert unavailable[0]["result"] == "pending"


def test_recheck_invalidates_when_owner_leaves_qsa(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization_body = create_verified_org(api, token)

    organization = db_session.get(Organization, uuid.UUID(organization_body["id"]))
    assert organization is not None
    organization.cnpj_next_check_at = utcnow() - timedelta(minutes=1)
    db_session.flush()

    lookup = FakeCnpjLookup(
        cnpj_record(
            qsa=(
                QsaPartner(
                    nome="OUTRA PESSOA",
                    cpf_masked="***999999**",
                    qualificacao="Sócio",
                ),
            )
        )
    )
    report = OrganizationVerificationService(db_session, get_settings(), lookup).recheck_due(
        limit=10
    )
    db_session.flush()
    assert report.invalid == 1
    db_session.refresh(organization)
    assert organization.verification_status == "invalid"


def test_no_sensitive_data_in_logs_or_audit(
    client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json=create_org_payload(),
    )
    assert response.status_code == 201

    audit_blob = " ".join(
        str(event.details) for event in db_session.scalars(select(AuditLog)).all()
    )
    log_blob = "\n".join(record.getMessage() for record in caplog.records)
    for blob in (audit_blob, log_blob, response.text):
        assert PARTNER_CPF not in blob
        assert "111.444.777-35" not in blob


# --- consulta e regras puras -------------------------------------------------


def brasilapi_payload() -> dict[str, object]:
    return {
        "cnpj": "19131243000197",
        "razao_social": "OPEN KNOWLEDGE BRASIL",
        "nome_fantasia": "REDE PELO CONHECIMENTO LIVRE",
        "descricao_situacao_cadastral": "ATIVA",
        "data_situacao_cadastral": "2013-10-03",
        "cnae_fiscal": 9430800,
        "cnae_fiscal_descricao": "Atividades de associações de defesa de direitos sociais",
        "cnaes_secundarios": [{"codigo": 9493600, "descricao": "Associativas"}],
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cep": "01311-902",
        "logradouro": "PAULISTA 37",
        "numero": "37",
        "bairro": "BELA VISTA",
        "qsa": [
            {
                "nome_socio": "LUIZ CARLOS PINHO GUEDES",
                "cnpj_cpf_do_socio": "***682847**",
                "qualificacao_socio": "Diretor",
            }
        ],
    }


def test_lookup_parses_payload_caches_and_masks_cpf() -> None:
    calls: list[str] = []

    def fetch(url: str, timeout: float) -> dict[str, object]:
        calls.append(url)
        return brasilapi_payload()

    lookup = BrasilApiCnpjLookup("https://example.test/cnpj", fetch_json=fetch)
    first = lookup.lookup("19.131.243/0001-97")
    second = lookup.lookup("19131243000197")

    assert first == second
    assert first.cnpj == "19131243000197"
    assert first.situacao_cadastral == "ATIVA"
    assert first.cnae_fiscal == "9430800"
    assert first.cep == "01311902"
    assert first.qsa[0].cpf_masked == "***682847**"
    assert "682847" in str(first.snapshot())
    assert len(calls) == 1


def test_lookup_retries_limited_and_maps_unavailable() -> None:
    calls: list[int] = []

    def fetch(url: str, timeout: float) -> dict[str, object]:
        calls.append(1)
        raise TimeoutError("timeout")

    lookup = BrasilApiCnpjLookup(
        "https://example.test/cnpj",
        attempts=2,
        fetch_json=fetch,
    )
    with pytest.raises(CnpjProviderUnavailable):
        lookup.lookup("19131243000197")
    assert len(calls) == 2


def test_lookup_maps_404_to_not_found() -> None:
    import urllib.error

    def fetch(url: str, timeout: float) -> dict[str, object]:
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    lookup = BrasilApiCnpjLookup("https://example.test/cnpj", fetch_json=fetch)
    with pytest.raises(CnpjNotFound):
        lookup.lookup("19131243000197")


def test_lookup_rejects_payload_for_another_cnpj() -> None:
    def fetch(url: str, timeout: float) -> dict[str, object]:
        payload = brasilapi_payload()
        payload["cnpj"] = "11222333000181"
        return payload

    lookup = BrasilApiCnpjLookup("https://example.test/cnpj", fetch_json=fetch)
    with pytest.raises(CnpjProviderUnavailable):
        lookup.lookup("19131243000197")


def test_lookup_rejects_invalid_payload() -> None:
    def fetch(url: str, timeout: float) -> dict[str, object]:
        return {"razao_social": "SEM CNAE"}

    lookup = BrasilApiCnpjLookup("https://example.test/cnpj", fetch_json=fetch)
    with pytest.raises(CnpjProviderUnavailable):
        lookup.lookup("19131243000197")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("11.222.333/0001-81", "11222333000181"),
        ("19131243000197", "19131243000197"),
    ],
)
def test_normalize_cnpj_accepts_formatting(value: str, expected: str) -> None:
    assert normalize_cnpj(value) == expected


@pytest.mark.parametrize("value", ["123", "00000000000000", "11222333000180", ""])
def test_normalize_cnpj_rejects_invalid(value: str) -> None:
    with pytest.raises(InvalidCnpj):
        normalize_cnpj(value)


def test_cpf_mask_matching_uses_middle_digits() -> None:
    assert cpf_masked_matches("***444777**", PARTNER_CPF)
    assert cpf_masked_matches(PARTNER_CPF, PARTNER_CPF)
    assert cpf_masked_matches("***.***.***-35", PARTNER_CPF)
    assert not cpf_masked_matches("***444778**", PARTNER_CPF)
    assert not cpf_masked_matches(None, PARTNER_CPF)


def test_names_match_accepts_full_name_and_abbreviation() -> None:
    assert names_match("Ana Souza", "ANA SOUZA")
    assert names_match("ANA SOUZA", "ANA MARIA SOUZA")
    assert not names_match("Ana", "ANA MARIA SOUZA")
    assert not names_match("Ana Souza", "OUTRA PESSOA")


def test_address_matches_by_municipality_or_cep_prefix() -> None:
    snapshot = cnpj_record().snapshot()
    assert address_matches(
        snapshot,
        city="Rio de Janeiro",
        state="RJ",
        postal_code="20541-004",
    )
    assert address_matches(
        snapshot,
        city=None,
        state="RJ",
        postal_code="20541-999",
    )
    assert not address_matches(
        snapshot,
        city="São Paulo",
        state="SP",
        postal_code=None,
    )
    assert not address_matches(
        snapshot,
        city=None,
        state="RJ",
        postal_code="01001-000",
    )
    assert not address_matches(snapshot, city=None, state=None, postal_code=None)


def test_mask_cnpj_hides_most_digits() -> None:
    masked = mask_cnpj("11222333000181")
    assert masked == "11.***.***/****-81"
    assert "2223330001" not in masked


def test_recheck_audit_does_not_store_plain_cpf(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_with_lookup(client, db_session, FakeCnpjLookup())
    _, token = login_with_partner(db_session)
    organization_body = create_verified_org(api, token)
    organization = db_session.get(Organization, uuid.UUID(organization_body["id"]))
    assert organization is not None
    organization.cnpj_next_check_at = utcnow() - timedelta(minutes=1)
    db_session.flush()

    OrganizationVerificationService(
        db_session,
        get_settings(),
        FakeCnpjLookup(),
    ).recheck_due(limit=10)
    db_session.flush()

    blob = " ".join(str(event.details) for event in db_session.scalars(select(AuditLog)).all())
    assert PARTNER_CPF not in blob
    assert PARTNER_CPF_MASKED in blob
