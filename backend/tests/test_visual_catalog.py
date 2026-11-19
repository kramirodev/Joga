"""Identidade visual por catálogo fechado (ADR 0029/0043)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.visual.models import UserVisualUnlock, VisualCatalogItem
from app.modules.visual.service import public_identity
from tests.helpers_results import make_token, make_user

BASE_KEYS = {
    "icon_key": "icon-sport-futebol-5x5",
    "frame_key": "frame-bronze",
    "accent_key": "accent-lime",
    "entry_key": "entry-invite-lobby",
    "emote_key": "emote-joinha",
    "badge_key": "badge-beta",
}


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def identity_payload(**overrides: str) -> dict[str, str]:
    return {**BASE_KEYS, **overrides}


def test_catalog_and_identity_require_working_defaults(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    catalog = api.get("/api/v1/catalog/visual")
    assert catalog.status_code == 200, catalog.text
    kinds = {item["kind"] for item in catalog.json()["items"]}
    assert kinds == {"icon", "frame", "accent", "entry", "emote", "badge"}

    current = api.get("/api/v1/me/visual", headers=bearer(token))
    assert current.status_code == 200, current.text
    body = current.json()
    assert body["icon_key"] == "icon-sport-futebol-5x5"
    assert body["frame_key"] == "frame-bronze"
    assert body["badge_key"] == "badge-beta"


def test_invalid_inactive_and_locked_items_are_rejected(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    invalid = api.put(
        "/api/v1/me/visual",
        headers=bearer(token),
        json=identity_payload(icon_key="icon-nao-existe"),
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": {"code": "invalid_visual_item"}}

    inactive_item = db_session.scalar(
        select(VisualCatalogItem).where(VisualCatalogItem.key == "icon-sport-volei-6x6")
    )
    assert inactive_item is not None
    inactive_item.active = False
    db_session.commit()

    inactive = api.put(
        "/api/v1/me/visual",
        headers=bearer(token),
        json=identity_payload(icon_key="icon-sport-volei-6x6"),
    )
    assert inactive.status_code == 400
    assert inactive.json() == {"detail": {"code": "invalid_visual_item"}}

    locked_item = VisualCatalogItem(
        key="icon-locked",
        kind="icon",
        name="Item bloqueado",
        asset_ref="icons/icon-locked.svg",
        unlock_state="xp",
        active=True,
    )
    db_session.add(locked_item)
    db_session.commit()

    locked = api.put(
        "/api/v1/me/visual",
        headers=bearer(token),
        json=identity_payload(icon_key="icon-locked"),
    )
    assert locked.status_code == 400
    assert locked.json() == {"detail": {"code": "visual_item_locked"}}

    db_session.add(UserVisualUnlock(user_id=user_id, item_id=locked_item.id, source="xp"))
    db_session.commit()

    unlocked = api.put(
        "/api/v1/me/visual",
        headers=bearer(token),
        json=identity_payload(icon_key="icon-locked"),
    )
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["icon_key"] == "icon-locked"


def test_two_users_keep_distinct_identities(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)

    assert (
        api.put(
            "/api/v1/me/visual",
            headers=bearer(first_token),
            json=identity_payload(icon_key="icon-sport-volei-6x6", accent_key="accent-azul"),
        ).status_code
        == 200
    )
    assert (
        api.put(
            "/api/v1/me/visual",
            headers=bearer(second_token),
            json=identity_payload(icon_key="icon-sport-futevolei-3x3", accent_key="accent-rosa"),
        ).status_code
        == 200
    )

    first_view = api.get("/api/v1/me/visual", headers=bearer(first_token)).json()
    second_view = api.get("/api/v1/me/visual", headers=bearer(second_token)).json()
    assert first_view["icon_key"] != second_view["icon_key"]
    assert first_view["accent_key"] == "accent-azul"
    assert second_view["accent_key"] == "accent-rosa"


def test_public_identity_exposes_only_four_visual_keys(
    client: TestClient, db_session: Session
) -> None:
    del client
    user_id = make_user(db_session)
    view = public_identity(db_session, user_id)

    assert set(view) == {"icon_key", "frame_key", "accent_key", "badge_key"}
    serialized = str(view)
    assert "@" not in serialized
    assert "phone" not in serialized
    assert "cpf" not in serialized


def test_my_visual_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/me/visual").status_code == 401
    assert client.put("/api/v1/me/visual", json=BASE_KEYS).status_code == 401


def test_identity_does_not_allow_free_text_or_urls(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.put(
        "/api/v1/me/visual",
        headers=bearer(token),
        json=identity_payload(icon_key="https://example.com/avatar.png"),
    )
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_visual_item"}}


def test_public_identity_never_reads_pii_from_users(
    client: TestClient, db_session: Session
) -> None:
    del client
    user = User(status="active")
    db_session.add(user)
    db_session.flush()
    view = public_identity(db_session, user.id)
    assert set(view) == {"icon_key", "frame_key", "accent_key", "badge_key"}
