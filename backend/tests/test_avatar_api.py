"""Testes de API do avatar e da importação temporária (Onda 1.7)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.avatar import get_instagram_importer
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.avatar.instagram import (
    InstagramPhoto,
    InstagramProfilePrivate,
)
from app.modules.avatar.models import UserAvatar
from app.modules.avatar.photos import process_avatar
from app.modules.avatar.storage import get_avatar_storage
from app.modules.identity.models import AuditLog, User
from app.modules.identity.sessions import SessionService
from app.modules.venues.storage import LocalPhotoStorage
from tests.test_avatar_instagram import PAGE_URL, image_bytes

BASE = "/api/v1/me/avatar"


@dataclass
class AvatarApi:
    client: TestClient
    session: Session
    importer: FakeImporter
    storage: LocalPhotoStorage
    settings: Settings
    tmp_path: object


class FakeImporter:
    def __init__(self, photo: InstagramPhoto) -> None:
        self.photo = photo
        self.calls: list[str] = []

    def fetch(self, raw_url: str) -> InstagramPhoto:
        self.calls.append(raw_url)
        return self.photo


class RaisingImporter:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[str] = []

    def fetch(self, raw_url: str) -> InstagramPhoto:
        self.calls.append(raw_url)
        raise self.error


def avatar_settings(tmp_path: object, mode: str = "scrape") -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        instagram_import_mode=mode,
        media_root=str(tmp_path),
    )


def make_photo() -> InstagramPhoto:
    processed = process_avatar(image_bytes(), max_bytes=5_000_000)
    return InstagramPhoto(
        username="alice",
        page_url=PAGE_URL,
        data=processed.data,
        content_type=processed.content_type,
        width=processed.width,
        height=processed.height,
    )


def make_user_with_tokens(session: Session, settings: Settings) -> tuple[uuid.UUID, str]:
    user = User(status="active")
    session.add(user)
    session.flush()
    tokens = SessionService(
        session,
        settings.token_hash_secret.get_secret_value(),
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_absolute_ttl_days=settings.refresh_absolute_ttl_days,
        refresh_idle_ttl_days=settings.refresh_idle_ttl_days,
    ).issue(user.id)
    session.commit()
    return user.id, tokens.access_token


@pytest.fixture
def avatar_api(client: TestClient, db_session: Session, tmp_path) -> AvatarApi:  # noqa: ANN001
    settings = avatar_settings(tmp_path)
    storage = LocalPhotoStorage(tmp_path)
    importer = FakeImporter(make_photo())

    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[get_avatar_storage] = lambda: storage
    client.app.dependency_overrides[get_instagram_importer] = lambda: importer
    return AvatarApi(client, db_session, importer, storage, settings, tmp_path)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_import_metadata_content_and_delete(avatar_api: AvatarApi) -> None:
    api = avatar_api
    user_id, token = make_user_with_tokens(api.session, api.settings)

    response = api.client.post(
        f"{BASE}/instagram",
        json={"url": PAGE_URL},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "source": "instagram",
        "avatar_url": "/api/v1/me/avatar/content",
        "username": "alice",
    }
    row = api.session.get(UserAvatar, user_id)
    assert row is not None and row.source == "instagram_scrape"
    assert row.storage_key is not None
    assert api.storage.read(row.storage_key).startswith(b"\xff\xd8\xff")

    metadata = api.client.get(BASE, headers=bearer(token))
    assert metadata.status_code == 200
    body = metadata.json()
    assert body["source"] == "instagram"
    assert body["username"] == "alice"
    assert body["width"] == 512 and body["height"] == 512
    assert "source_url" not in body

    content = api.client.get(f"{BASE}/content", headers=bearer(token))
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/jpeg"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["cache-control"] == "no-store"
    assert content.content.startswith(b"\xff\xd8\xff")

    assert api.client.get(f"{BASE}/content").status_code == 401

    deleted = api.client.delete(f"{BASE}/instagram", headers=bearer(token))
    assert deleted.status_code == 204
    assert api.session.get(UserAvatar, user_id) is None
    assert not (api.tmp_path / str(row.storage_key)).exists()  # type: ignore[operator]
    assert api.client.delete(f"{BASE}/instagram", headers=bearer(token)).status_code == 204


def test_delete_and_content_do_not_cross_users(avatar_api: AvatarApi) -> None:
    api = avatar_api
    user_a, token_a = make_user_with_tokens(api.session, api.settings)
    user_b, token_b = make_user_with_tokens(api.session, api.settings)

    created = api.client.post(f"{BASE}/instagram", json={"url": PAGE_URL}, headers=bearer(token_b))
    assert created.status_code == 200
    row_b = api.session.get(UserAvatar, user_b)
    assert row_b is not None

    # A remove o próprio avatar (que não existe) e não toca no de B.
    assert api.client.delete(f"{BASE}/instagram", headers=bearer(token_a)).status_code == 204
    api.session.refresh(row_b)
    assert api.session.get(UserAvatar, user_b) is not None

    other_content = api.client.get(
        f"/api/v1/users/{user_b}/avatar/content", headers=bearer(token_a)
    )
    assert other_content.status_code == 200
    assert other_content.content.startswith(b"\xff\xd8\xff")

    missing = api.client.get(f"/api/v1/users/{user_a}/avatar/content", headers=bearer(token_a))
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "avatar_not_found"


def test_flag_off_returns_404_without_network(avatar_api: AvatarApi) -> None:
    api = avatar_api
    _, token = make_user_with_tokens(api.session, api.settings)
    api.client.app.dependency_overrides[get_settings] = lambda: avatar_settings(
        api.tmp_path, mode="off"
    )

    response = api.client.post(f"{BASE}/instagram", json={"url": PAGE_URL}, headers=bearer(token))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "instagram_import_disabled"
    assert api.importer.calls == []


def test_rate_limit_is_five_per_hour(avatar_api: AvatarApi) -> None:
    api = avatar_api
    user_id, token = make_user_with_tokens(api.session, api.settings)

    for _ in range(5):
        response = api.client.post(
            f"{BASE}/instagram", json={"url": PAGE_URL}, headers=bearer(token)
        )
        assert response.status_code == 200, response.text

    limited = api.client.post(f"{BASE}/instagram", json={"url": PAGE_URL}, headers=bearer(token))
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limited"
    assert limited.headers["retry-after"]
    audits = api.session.scalars(
        select(AuditLog).where(
            AuditLog.actor_user_id == user_id,
            AuditLog.action == "avatar.instagram_import",
        )
    ).all()
    assert any((event.details or {}).get("outcome") == "rate_limited" for event in audits)


def test_private_profile_maps_to_409(avatar_api: AvatarApi) -> None:
    api = avatar_api
    _, token = make_user_with_tokens(api.session, api.settings)
    api.client.app.dependency_overrides[get_instagram_importer] = lambda: RaisingImporter(
        InstagramProfilePrivate("privado")
    )

    response = api.client.post(f"{BASE}/instagram", json={"url": PAGE_URL}, headers=bearer(token))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "instagram_profile_private"


def test_metadata_without_avatar_is_empty(avatar_api: AvatarApi) -> None:
    api = avatar_api
    _, token = make_user_with_tokens(api.session, api.settings)

    response = api.client.get(BASE, headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "source": None,
        "avatar_url": None,
        "username": None,
        "width": None,
        "height": None,
        "size_bytes": None,
        "updated_at": None,
    }
