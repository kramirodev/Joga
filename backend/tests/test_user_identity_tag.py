"""Tag pública do jogador e canonização do nome de exibição."""

from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.text import normalize_display_name
from app.modules.email.sender import FakeSender
from app.modules.identity.models import User
from app.modules.identity.tags import next_available_tag, tag_from_uuid
from app.modules.identity.user_admin import create_user
from app.modules.profile.models import UserProfile
from tests.email_helpers import PASSWORD, bearer, fast_password_service, register_flow
from tests.helpers_results import make_user


def test_normalize_display_name_collapses_spaces_and_uppercases() -> None:
    assert normalize_display_name("  joão   da  silva ") == "JOÃO DA SILVA"
    assert normalize_display_name("ção 🎾") == "ÇÃO 🎾"
    assert normalize_display_name("   ") is None
    assert normalize_display_name(None) is None
    assert len(normalize_display_name("ß" * 60) or "") == 60


def test_tag_is_derived_from_uuid_and_extends_on_collision(db_session: Session) -> None:
    first = uuid.UUID("aaaaaaaa-1000-4000-8000-000000000001")
    second = uuid.UUID("aaaaaaaa-2000-4000-8000-000000000002")

    assert tag_from_uuid(first) == "#AAAAAAAA"
    assert tag_from_uuid(first, 10) == "#AAAAAAAA10"
    db_session.add(User(id=first, status="active", tag=tag_from_uuid(first)))
    db_session.flush()

    assert next_available_tag(db_session, second) == "#AAAAAAAA20"


def test_registration_normalizes_name_and_profile_returns_tag(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    registered = register_flow(
        email_api,
        db_session,
        sender,
        "nome-canonico@example.com",
        display_name="  joão   da  silva ",
    )
    user_id = uuid.UUID(str(registered["user"]["id"]))

    profile = db_session.get(UserProfile, user_id)
    user = db_session.get(User, user_id)
    assert profile is not None and profile.display_name == "JOÃO DA SILVA"
    assert user is not None and re.fullmatch(r"#[0-9A-F]{8,12}", user.tag)

    response = email_api.get(
        "/api/v1/me/profile",
        headers=bearer(str(registered["access_token"])),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "JOÃO DA SILVA"
    assert body["tag"] == user.tag


def test_admin_creation_normalizes_name_and_assigns_tag(db_session: Session) -> None:
    actor = make_user(db_session)
    created = create_user(
        db_session,
        email="admin-criado@example.com",
        password=PASSWORD,
        display_name="  admin   teste ",
        verify_email=True,
        passwords=fast_password_service(),
        actor_user_id=actor,
        reason="teste de canonização",
    )

    profile = db_session.get(UserProfile, created.id)
    assert profile is not None and profile.display_name == "ADMIN TESTE"
    user = db_session.get(User, created.id)
    assert user is not None and re.fullmatch(r"#[0-9A-F]{8,12}", user.tag)
