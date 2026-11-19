"""Administração de usuários por platform_admin."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.email_auth import get_password_service
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.email.models import EmailDelivery, UserEmail
from app.modules.identity.models import AuditLog
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.profile.models import UserProfile
from tests.email_helpers import fast_password_service, seed_user_with_email
from tests.helpers_results import make_token, make_user

ADMIN_EMAIL = "admin@joga.example"
PLAYER_EMAIL = "jogador@joga.example"
PASSWORD = "SenhaSeguraBeta123"


def api_client(
    client: TestClient,
    db_session: Session,
    *,
    admin_id: UUID | None = None,
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    settings = Settings(
        _env_file=None,
        platform_admins=str(admin_id) if admin_id is not None else "",
        ticket_purchase_enabled=True,
    )
    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[get_password_service] = fast_password_service
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_setup(db_session: Session) -> tuple[UUID, dict[str, str]]:
    admin_id = make_user(db_session)
    return admin_id, bearer(make_token(db_session, admin_id))


def test_admin_users_negative_authorization(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    assert api.get("/api/v1/admin/users").status_code == 401

    organization = Organization(name="Arena Teste")
    owner_id = make_user(db_session)
    operator_id = make_user(db_session)
    player_id = make_user(db_session)
    db_session.add(organization)
    db_session.flush()
    db_session.add_all(
        [
            OrganizationMembership(organization_id=organization.id, user_id=owner_id, role="OWNER"),
            OrganizationMembership(
                organization_id=organization.id, user_id=operator_id, role="OPERATOR"
            ),
        ]
    )
    db_session.commit()

    for user_id in (owner_id, operator_id, player_id):
        response = api.get(
            "/api/v1/admin/users",
            headers=bearer(make_token(db_session, user_id)),
        )
        assert response.status_code == 403
        assert response.json() == {"detail": {"code": "forbidden"}}


def test_create_user_and_detail_hide_secrets(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    created = api.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": ADMIN_EMAIL,
            "password": PASSWORD,
            "display_name": "Admin",
            "verify_email": True,
            "reason": "cadastro operacional",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["email_verified"] is True
    assert body["status"] == "active"
    for forbidden in ("password", "password_hash", "cpf_ciphertext", "otp", "token"):
        assert forbidden not in body

    detail = api.get(f"/api/v1/admin/users/{body['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["email"] == ADMIN_EMAIL
    assert "password_hash" not in detail.text
    assert "cpf_ciphertext" not in detail.text

    missing_reason = api.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "outro@joga.example",
            "password": PASSWORD,
            "verify_email": False,
        },
    )
    assert missing_reason.status_code == 422


def test_detail_masks_cpf(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    target = make_user(db_session)
    db_session.add(
        UserProfile(
            user_id=target,
            display_name="Jogador",
            cpf_ciphertext=b"\x00" * 40,
            cpf_key_id="test-key",
            cpf_last2="99",
        )
    )
    db_session.commit()

    detail = api.get(f"/api/v1/admin/users/{target}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["cpf_masked"] == "***.***.***-99"
    assert "cpf_ciphertext" not in detail.text


def test_search_and_pagination(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    for index in range(3):
        user_id, _ = seed_user_with_email(db_session, f"busca{index}@joga.example")
        db_session.add(UserProfile(user_id=user_id, display_name=f"Busca {index}"))
    db_session.commit()

    found = api.get("/api/v1/admin/users?q=busca1", headers=headers)
    assert found.status_code == 200, found.text
    assert found.json()["total"] == 1
    assert found.json()["users"][0]["email"] == "busca1@joga.example"

    page = api.get("/api/v1/admin/users?page=1&page_size=2", headers=headers)
    assert page.status_code == 200
    assert len(page.json()["users"]) == 2
    assert page.json()["total"] == 4  # admin + 3 jogadores


def test_email_change_notifies_old_address_and_revokes_sessions(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    target, _ = seed_user_with_email(db_session, PLAYER_EMAIL)
    old_token = make_token(db_session, target)
    api = api_client(client, db_session, admin_id=admin_id)

    changed = api.patch(
        f"/api/v1/admin/users/{target}/email",
        headers=headers,
        json={"email": "novo@joga.example", "reason": "correção cadastral"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["email"] == "novo@joga.example"

    old_credential = db_session.scalar(
        select(UserEmail).where(UserEmail.email_normalized == PLAYER_EMAIL)
    )
    new_credential = db_session.scalar(
        select(UserEmail).where(UserEmail.email_normalized == "novo@joga.example")
    )
    assert old_credential is not None and old_credential.released_at is not None
    assert new_credential is not None and new_credential.verified_at is not None

    notice = db_session.scalar(
        select(EmailDelivery).where(EmailDelivery.kind == "email_change_notice")
    )
    assert notice is not None

    assert api.get("/api/v1/auth/me", headers=bearer(old_token)).status_code == 401


def test_suspend_reactivate_revoke_and_append_only_audit(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    target, _ = seed_user_with_email(db_session, PLAYER_EMAIL)
    api = api_client(client, db_session, admin_id=admin_id)

    suspended = api.post(
        f"/api/v1/admin/users/{target}/suspend",
        headers=headers,
        json={"reason": "abuso confirmado", "until": "2027-01-01T00:00:00Z"},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["suspended_until"] is not None

    reactivated = api.post(
        f"/api/v1/admin/users/{target}/reactivate",
        headers=headers,
        json={"reason": "recurso aceito"},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["status"] == "active"

    make_token(db_session, target)
    revoked = api.post(
        f"/api/v1/admin/users/{target}/sessions/revoke",
        headers=headers,
        json={"reason": "dispositivo perdido"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] >= 1

    audit = api.get(f"/api/v1/admin/users/{target}/audit", headers=headers)
    assert audit.status_code == 200, audit.text
    actions = [event["action"] for event in audit.json()["events"]]
    assert actions == [
        "admin.user.suspend",
        "admin.user.reactivate",
        "admin.user.sessions_revoke",
    ]
    assert all(event["reason"] for event in audit.json()["events"])

    persisted = db_session.scalars(
        select(AuditLog).where(AuditLog.resource_id == str(target))
    ).all()
    assert len(persisted) >= 3


def test_password_reset_never_returns_code_or_hash(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    target, _ = seed_user_with_email(db_session, PLAYER_EMAIL)
    api = api_client(client, db_session, admin_id=admin_id)

    response = api.post(
        f"/api/v1/admin/users/{target}/password-reset",
        headers=headers,
        json={"reason": "suporte ao jogador"},
    )
    assert response.status_code == 204, response.text
    assert response.content == b""

    delivery = db_session.scalar(
        select(EmailDelivery).where(EmailDelivery.kind == "password_reset")
    )
    assert delivery is not None
    assert "123456" not in response.text


def test_missing_reason_is_rejected(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    target = make_user(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    missing = api.post(
        f"/api/v1/admin/users/{target}/suspend",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    blank = api.post(
        f"/api/v1/admin/users/{target}/suspend",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422
    assert blank.json() == {"detail": {"code": "reason_required"}}
