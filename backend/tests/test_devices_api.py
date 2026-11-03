"""Testes dos dispositivos e da revogação de sessões por dispositivo."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.auth import get_session
from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.modules.identity.devices import DeviceService
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService


@pytest.fixture
def api(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_user_with_device(
    session: Session,
    name: str,
) -> tuple[User, str, str]:
    user = User(status="active")
    session.add(user)
    session.flush()
    device = DeviceService(session).register(user.id, name, "android")
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id, device_id=device.id)
    session.commit()
    return user, device.id, tokens.access_token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_and_revoke_device(api: TestClient, db_session: Session) -> None:
    _, device_id, access = make_user_with_device(db_session, "Moto G")

    listed = api.get("/api/v1/auth/devices", headers=bearer(access))
    assert listed.status_code == 200
    assert len(listed.json()["devices"]) == 1
    assert listed.json()["devices"][0]["name"] == "Moto G"

    revoked = api.delete(f"/api/v1/auth/devices/{device_id}", headers=bearer(access))
    assert revoked.status_code == 204
    assert api.get("/api/v1/auth/me", headers=bearer(access)).status_code == 401
    listed_after = api.get("/api/v1/auth/devices", headers=bearer(access))
    assert listed_after.status_code == 401


def test_other_user_cannot_revoke_device(api: TestClient, db_session: Session) -> None:
    _, device_id, _ = make_user_with_device(db_session, "Moto G")
    _, _, other_access = make_user_with_device(db_session, "Outro")

    response = api.delete(
        f"/api/v1/auth/devices/{device_id}",
        headers=bearer(other_access),
    )

    assert response.status_code == 404
