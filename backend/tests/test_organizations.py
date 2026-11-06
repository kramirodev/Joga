"""Testes HTTP de organizações, papéis, BOLA e auditoria (Fase 11)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_organization(api: TestClient, token: str, name: str = "Arena Teste") -> dict:
    response = api.post(
        "/api/v1/organizations",
        headers=bearer(token),
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_member(
    api: TestClient,
    token: str,
    organization_id: str,
    user_id: uuid.UUID,
    role: str,
) -> dict:
    response = api.post(
        f"/api/v1/organizations/{organization_id}/members",
        headers=bearer(token),
        json={"user_id": str(user_id), "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_venue(
    api: TestClient,
    token: str,
    organization_id: str,
    name: str = "Quadra Central",
) -> dict:
    response = api.post(
        f"/api/v1/organizations/{organization_id}/venues",
        headers=bearer(token),
        json={"name": name, "city": "Rio de Janeiro", "state": "rj"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_and_shared_identity_across_organizations(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)

    first_org = create_organization(api, first_token, "Arena do Primeiro")
    assert first_org["role"] == "OWNER"

    second_org = create_organization(api, second_token, "Arena do Segundo")
    add_member(api, first_token, first_org["id"], second, "OPERATOR")

    listed = api.get("/api/v1/organizations", headers=bearer(second_token))
    assert listed.status_code == 200
    roles = {item["id"]: item["role"] for item in listed.json()["organizations"]}
    assert roles == {
        second_org["id"]: "OWNER",
        first_org["id"]: "OPERATOR",
    }

    members = api.get(
        f"/api/v1/organizations/{first_org['id']}/members",
        headers=bearer(second_token),
    )
    assert members.status_code == 200
    assert {item["user_id"] for item in members.json()["members"]} == {
        str(first),
        str(second),
    }


def test_cross_organization_access_is_denied_with_404(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)
    first_org = create_organization(api, first_token, "Arena A")
    second_org = create_organization(api, second_token, "Arena B")
    first_venue = create_venue(api, first_token, first_org["id"], "Quadra A")
    second_venue = create_venue(api, second_token, second_org["id"], "Quadra B")

    base = f"/api/v1/organizations/{first_org['id']}"
    attempts = [
        api.get(base, headers=bearer(second_token)),
        api.patch(base, headers=bearer(second_token), json={"name": "Invasão"}),
        api.get(f"{base}/members", headers=bearer(second_token)),
        api.post(
            f"{base}/members",
            headers=bearer(second_token),
            json={"user_id": str(first), "role": "OPERATOR"},
        ),
        api.get(f"{base}/venues", headers=bearer(second_token)),
        api.post(
            f"{base}/venues",
            headers=bearer(second_token),
            json={"name": "Quadra Invasora"},
        ),
        api.get(f"{base}/audit", headers=bearer(second_token)),
    ]
    for response in attempts:
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": {"code": "organization_not_found"}}

    # IDs de estabelecimentos de outra organização não podem ser reutilizados.
    confused = [
        api.get(
            f"{base}/venues/{second_venue['id']}",
            headers=bearer(first_token),
        ),
        api.patch(
            f"{base}/venues/{second_venue['id']}",
            headers=bearer(first_token),
            json={"name": "Alterada"},
        ),
        api.get(
            f"/api/v1/organizations/{second_org['id']}/venues/{first_venue['id']}",
            headers=bearer(second_token),
        ),
    ]
    for response in confused:
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": {"code": "venue_not_found"}}

    # A organização original permanece intacta.
    unchanged = api.get(base, headers=bearer(first_token))
    assert unchanged.status_code == 200
    assert unchanged.json()["name"] == "Arena A"


def test_operator_can_read_and_manage_venues_but_not_members(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    owner = make_user(db_session)
    operator = make_user(db_session)
    other = make_user(db_session)
    owner_token = make_token(db_session, owner)
    operator_token = make_token(db_session, operator)
    org = create_organization(api, owner_token)
    add_member(api, owner_token, org["id"], operator, "OPERATOR")

    assert (
        api.get(
            f"/api/v1/organizations/{org['id']}",
            headers=bearer(operator_token),
        ).status_code
        == 200
    )
    assert (
        api.get(
            f"/api/v1/organizations/{org['id']}/members",
            headers=bearer(operator_token),
        ).status_code
        == 200
    )
    assert (
        api.patch(
            f"/api/v1/organizations/{org['id']}",
            headers=bearer(operator_token),
            json={"name": "Novo nome"},
        ).status_code
        == 403
    )
    assert api.post(
        f"/api/v1/organizations/{org['id']}/members",
        headers=bearer(operator_token),
        json={"user_id": str(other), "role": "OPERATOR"},
    ).json() == {"detail": {"code": "forbidden"}}
    assert (
        api.patch(
            f"/api/v1/organizations/{org['id']}/members/{other}",
            headers=bearer(operator_token),
            json={"role": "ADMIN"},
        ).status_code
        == 403
    )
    assert (
        api.delete(
            f"/api/v1/organizations/{org['id']}/members/{other}",
            headers=bearer(operator_token),
        ).status_code
        == 403
    )
    assert (
        api.get(
            f"/api/v1/organizations/{org['id']}/audit",
            headers=bearer(operator_token),
        ).status_code
        == 403
    )

    venue = create_venue(api, operator_token, org["id"])
    updated = api.patch(
        f"/api/v1/organizations/{org['id']}/venues/{venue['id']}",
        headers=bearer(operator_token),
        json={"name": "Quadra Renomeada", "state": "sp"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Quadra Renomeada"
    assert updated.json()["state"] == "SP"


def test_admin_cannot_manage_owners_or_other_admins(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    owner = make_user(db_session)
    admin = make_user(db_session)
    operator = make_user(db_session)
    second_admin = make_user(db_session)
    second_owner = make_user(db_session)
    owner_token = make_token(db_session, owner)
    admin_token = make_token(db_session, admin)
    org = create_organization(api, owner_token)
    add_member(api, owner_token, org["id"], admin, "ADMIN")
    add_member(api, owner_token, org["id"], operator, "OPERATOR")
    add_member(api, owner_token, org["id"], second_admin, "ADMIN")

    # Administrador atualiza a organização e consulta a auditoria.
    assert (
        api.patch(
            f"/api/v1/organizations/{org['id']}",
            headers=bearer(admin_token),
            json={"name": "Arena Administrada"},
        ).status_code
        == 200
    )
    assert (
        api.get(
            f"/api/v1/organizations/{org['id']}/audit",
            headers=bearer(admin_token),
        ).status_code
        == 200
    )

    # Administrador gerencia operadores.
    promoted = api.patch(
        f"/api/v1/organizations/{org['id']}/members/{operator}",
        headers=bearer(admin_token),
        json={"role": "OPERATOR"},
    )
    assert promoted.status_code == 200
    assert (
        api.delete(
            f"/api/v1/organizations/{org['id']}/members/{operator}",
            headers=bearer(admin_token),
        ).status_code
        == 204
    )

    # Administrador não cria administradores/proprietários nem altera pares.
    for payload in (
        {"user_id": str(second_owner), "role": "OWNER"},
        {"user_id": str(second_owner), "role": "ADMIN"},
    ):
        response = api.post(
            f"/api/v1/organizations/{org['id']}/members",
            headers=bearer(admin_token),
            json=payload,
        )
        assert response.status_code == 403, response.text
        assert response.json() == {"detail": {"code": "role_not_allowed"}}

    for target, role in ((owner, "OPERATOR"), (second_admin, "OPERATOR")):
        response = api.patch(
            f"/api/v1/organizations/{org['id']}/members/{target}",
            headers=bearer(admin_token),
            json={"role": role},
        )
        assert response.status_code == 403, response.text
        assert response.json() == {"detail": {"code": "role_not_allowed"}}

    for target in (owner, second_admin):
        response = api.delete(
            f"/api/v1/organizations/{org['id']}/members/{target}",
            headers=bearer(admin_token),
        )
        assert response.status_code == 403, response.text
        assert response.json() == {"detail": {"code": "role_not_allowed"}}


def test_last_owner_cannot_be_removed_or_demoted(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    owner = make_user(db_session)
    successor = make_user(db_session)
    owner_token = make_token(db_session, owner)
    org = create_organization(api, owner_token)

    demote = api.patch(
        f"/api/v1/organizations/{org['id']}/members/{owner}",
        headers=bearer(owner_token),
        json={"role": "ADMIN"},
    )
    assert demote.status_code == 409
    assert demote.json() == {"detail": {"code": "last_owner_required"}}

    leave = api.delete(
        f"/api/v1/organizations/{org['id']}/members/{owner}",
        headers=bearer(owner_token),
    )
    assert leave.status_code == 409
    assert leave.json() == {"detail": {"code": "last_owner_required"}}

    add_member(api, owner_token, org["id"], successor, "OWNER")
    changed = api.patch(
        f"/api/v1/organizations/{org['id']}/members/{owner}",
        headers=bearer(owner_token),
        json={"role": "ADMIN"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "ADMIN"

    members = api.get(
        f"/api/v1/organizations/{org['id']}/members",
        headers=bearer(owner_token),
    )
    assert members.status_code == 200
    owners = [item for item in members.json()["members"] if item["role"] == "OWNER"]
    assert [item["user_id"] for item in owners] == [str(successor)]


def test_duplicate_and_missing_members_are_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    owner = make_user(db_session)
    member = make_user(db_session)
    owner_token = make_token(db_session, owner)
    org = create_organization(api, owner_token)
    add_member(api, owner_token, org["id"], member, "OPERATOR")

    duplicate = api.post(
        f"/api/v1/organizations/{org['id']}/members",
        headers=bearer(owner_token),
        json={"user_id": str(member), "role": "OPERATOR"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "member_already_exists"}}

    missing = api.post(
        f"/api/v1/organizations/{org['id']}/members",
        headers=bearer(owner_token),
        json={"user_id": str(uuid.uuid4()), "role": "OPERATOR"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": {"code": "user_not_found"}}

    suspended = User(status="suspended")
    db_session.add(suspended)
    db_session.flush()
    inactive = api.post(
        f"/api/v1/organizations/{org['id']}/members",
        headers=bearer(owner_token),
        json={"user_id": str(suspended.id), "role": "OPERATOR"},
    )
    assert inactive.status_code == 409
    assert inactive.json() == {"detail": {"code": "user_not_active"}}


def test_audit_is_scoped_and_records_administrative_actions(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)
    first_org = create_organization(api, first_token, "Arena Auditada")
    second_org = create_organization(api, second_token, "Outra Arena")
    add_member(api, first_token, first_org["id"], second, "OPERATOR")
    api.patch(
        f"/api/v1/organizations/{first_org['id']}",
        headers=bearer(first_token),
        json={"name": "Arena Renomeada"},
    )
    venue = create_venue(api, first_token, first_org["id"], "Quadra 1")
    api.patch(
        f"/api/v1/organizations/{first_org['id']}/venues/{venue['id']}",
        headers=bearer(first_token),
        json={"city": "Niterói"},
    )

    audit = api.get(
        f"/api/v1/organizations/{first_org['id']}/audit",
        headers=bearer(first_token),
    )
    assert audit.status_code == 200
    events = audit.json()["audit"]
    actions = {event["action"] for event in events}
    assert {
        "organization.created",
        "organization.updated",
        "membership.added",
        "venue.created",
        "venue.updated",
    } <= actions
    assert all(event["actor_user_id"] == str(first) for event in events)
    assert all(
        event["resource_type"] in {"organization", "organization_membership", "venue"}
        for event in events
    )

    # A trilha de uma organização não aparece na outra.
    other_audit = api.get(
        f"/api/v1/organizations/{second_org['id']}/audit",
        headers=bearer(second_token),
    )
    assert other_audit.status_code == 200
    other_actions = {event["action"] for event in other_audit.json()["audit"]}
    assert "venue.created" not in other_actions
    assert "venue.updated" not in other_actions

    limited = api.get(
        f"/api/v1/organizations/{first_org['id']}/audit?limit=2&offset=0",
        headers=bearer(first_token),
    )
    assert limited.status_code == 200
    assert len(limited.json()["audit"]) == 2
    assert limited.json()["limit"] == 2
    assert limited.json()["offset"] == 0


def test_organizations_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/organizations")
    assert response.status_code == 401
    assert response.json() == {"detail": {"code": "invalid_token"}}
