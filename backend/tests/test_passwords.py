"""Hash Argon2id, política de senha e caminho de e-mail inexistente."""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from sqlalchemy.orm import Session

from app.modules.identity.email_accounts import (
    EmailAccountService,
    InvalidCredentials,
)
from app.modules.identity.passwords import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PasswordPolicyError,
    PasswordService,
)
from tests.email_helpers import PASSWORD, seed_user_with_email


def test_default_hash_is_argon2id_with_conservative_parameters() -> None:
    service = PasswordService()
    digest = service.hash(PASSWORD)
    assert digest.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert service.verify(digest, PASSWORD) is True
    assert service.verify(digest, PASSWORD + "x") is False
    assert service.needs_rehash(digest) is False


def test_invalid_hash_never_authenticates() -> None:
    service = PasswordService()
    assert service.verify("not-a-phc-hash", PASSWORD) is False


def test_fast_hash_needs_rehash_and_verifies() -> None:
    hasher = PasswordHasher(memory_cost=1024, time_cost=1, parallelism=1)
    service = PasswordService(hasher, dummy_hash=hasher.hash("dummy"))
    digest = service.hash(PASSWORD)
    assert service.verify(digest, PASSWORD) is True
    assert PasswordService().needs_rehash(digest) is True


@pytest.mark.parametrize(
    "password",
    [
        "curta",
        "a" * (PASSWORD_MAX_LENGTH + 1),
        "senha12345",
        "password123",
    ],
)
def test_policy_rejects_short_long_or_common_passwords(password: str) -> None:
    service = PasswordService()
    with pytest.raises(PasswordPolicyError):
        service.validate(password, "jogador@example.com")


def test_policy_rejects_email_and_local_part() -> None:
    service = PasswordService()
    with pytest.raises(PasswordPolicyError):
        service.validate("jogador@example.com", "jogador@example.com")
    with pytest.raises(PasswordPolicyError):
        service.validate("jogador", "jogador@example.com")


def test_policy_accepts_passphrase_without_symbol_requirements() -> None:
    service = PasswordService()
    service.validate("uma frase longa e fácil de lembrar", "jogador@example.com")
    assert PASSWORD_MIN_LENGTH == 10


def test_unknown_email_runs_dummy_verification(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passwords = PasswordService()
    calls: list[str] = []
    monkeypatch.setattr(passwords, "verify_dummy", lambda value: calls.append(value))
    service = EmailAccountService(
        db_session,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        passwords,
        "test-secret",
    )

    with pytest.raises(InvalidCredentials):
        service.authenticate("nao-existe@example.com", "qualquer-senha")

    assert calls == ["qualquer-senha"]


def test_existing_email_runs_real_verification(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_user_with_email(db_session, "existe@example.com", password=PASSWORD)
    passwords = PasswordService()
    dummy_calls: list[str] = []
    monkeypatch.setattr(passwords, "verify_dummy", lambda value: dummy_calls.append(value))
    service = EmailAccountService(
        db_session,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        passwords,
        "test-secret",
    )

    with pytest.raises(InvalidCredentials):
        service.authenticate("existe@example.com", "senha-errada")

    assert dummy_calls == []
