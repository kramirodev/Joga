"""CPF único por conta: contrato 409, privacidade e índice parcial (ADR 0065)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import AuditLog, User
from app.modules.profile.cpf import hash_cpf
from app.modules.profile.models import UserProfile
from tests.compliance_helpers import TEST_CPF, cpf_key_kwargs
from tests.helpers_results import make_token, make_user
from tests.test_ticket_settlement import bearer

OTHER_CPF = "11144477735"


def cpf_settings() -> Settings:
    return Settings(_env_file=None, environment="test", **cpf_key_kwargs())


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = cpf_settings
    return client


def test_one_cpf_belongs_to_one_account(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    first_user = make_user(db_session)
    second_user = make_user(db_session)
    first_token = make_token(db_session, first_user)
    second_token = make_token(db_session, second_user)

    saved = api.put("/api/v1/me/cpf", headers=bearer(first_token), json={"cpf": TEST_CPF})
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"cpf_present": True, "cpf_masked": "***.***.***-25"}

    duplicate = api.put(
        "/api/v1/me/cpf",
        headers=bearer(second_token),
        json={"cpf": "529.982.247-25"},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json() == {"detail": {"code": "cpf_already_registered"}}

    available = api.put("/api/v1/me/cpf", headers=bearer(second_token), json={"cpf": OTHER_CPF})
    assert available.status_code == 200, available.text
    assert available.json()["cpf_masked"] == "***.***.***-35"

    first_profile = db_session.get(UserProfile, first_user)
    second_profile = db_session.get(UserProfile, second_user)
    assert first_profile is not None and second_profile is not None
    assert first_profile.cpf_hash == hash_cpf(TEST_CPF, cpf_settings())
    assert second_profile.cpf_hash == hash_cpf(OTHER_CPF, cpf_settings())
    assert first_profile.cpf_hash != second_profile.cpf_hash

    # Atualizar o perfil para um CPF já usado também colide e preserva o atual.
    conflict = api.put(
        "/api/v1/me/cpf",
        headers=bearer(first_token),
        json={"cpf": OTHER_CPF},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json() == {"detail": {"code": "cpf_already_registered"}}
    db_session.refresh(first_profile)
    assert first_profile.cpf_hash == hash_cpf(TEST_CPF, cpf_settings())
    assert api.get("/api/v1/me/cpf", headers=bearer(first_token)).json()["cpf_masked"] == (
        "***.***.***-25"
    )


def test_null_cpf_does_not_collide(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    first_token = make_token(db_session, make_user(db_session))
    second_token = make_token(db_session, make_user(db_session))

    for token, name in ((first_token, "Ana"), (second_token, "Bia")):
        response = api.put(
            "/api/v1/me/profile",
            headers=bearer(token),
            json={"display_name": name},
        )
        assert response.status_code == 200, response.text

    hashes = list(
        db_session.scalars(
            select(UserProfile.cpf_hash).where(
                UserProfile.display_name.in_(["Ana", "Bia"]),
            )
        )
    )
    assert len(hashes) == 2
    assert set(hashes) == {None}


def test_partial_unique_index_rejects_duplicate_but_accepts_nulls(
    db_session: Session,
) -> None:
    first = User(status="active")
    second = User(status="active")
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add_all(
        [
            UserProfile(user_id=first.id),
            UserProfile(user_id=second.id),
        ]
    )
    db_session.flush()  # dois CPFs nulos convivem no índice parcial

    digest = "a" * 64
    first_profile = db_session.get(UserProfile, first.id)
    second_profile = db_session.get(UserProfile, second.id)
    assert first_profile is not None and second_profile is not None
    for profile in (first_profile, second_profile):
        profile.cpf_ciphertext = b"x" * 28
        profile.cpf_key_id = "test-v1"
        profile.cpf_last2 = "25"
        profile.cpf_hash = digest
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_cpf_and_hash_never_appear_in_payloads_logs_or_audit(
    client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    api = api_client(client, db_session)
    owner = make_user(db_session)
    other = make_user(db_session)
    owner_token = make_token(db_session, owner)
    other_token = make_token(db_session, other)

    saved = api.put("/api/v1/me/cpf", headers=bearer(owner_token), json={"cpf": TEST_CPF})
    duplicate = api.put("/api/v1/me/cpf", headers=bearer(other_token), json={"cpf": TEST_CPF})
    read = api.get("/api/v1/me/cpf", headers=bearer(owner_token))
    assert saved.status_code == 200
    assert duplicate.status_code == 409
    assert read.status_code == 200

    expected_hash = hash_cpf(TEST_CPF, cpf_settings())
    audit_blob = " ".join(
        str(event.details)
        for event in db_session.scalars(select(AuditLog).where(AuditLog.actor_user_id == owner))
    )
    log_blob = "\n".join(record.getMessage() for record in caplog.records)
    for blob in (saved.text, duplicate.text, read.text, audit_blob, log_blob):
        assert TEST_CPF not in blob
        assert "529.982.247-25" not in blob
        assert expected_hash not in blob
