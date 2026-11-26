"""Política de caracteres de nomes públicos, senha e texto livre.

Cobre a fonte da verdade no servidor: nome de jogador, nome de clã/organização/
quadra, senha e textos com emoji permitido pelo produto.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1 import clans, email_auth, organizations, venues
from app.api.v1 import profile as profile_api
from app.core.text import (
    InvalidDisplayNameChars,
    InvalidDisplayNameLength,
    InvalidNameChars,
    InvalidNameLength,
    canonicalize_clan_name,
    canonicalize_display_name,
)
from app.infrastructure.database.dependency import get_session
from app.modules.identity.passwords import (
    PASSWORD_MAX_LENGTH,
    InvalidPasswordChars,
    InvalidPasswordWhitespace,
    PasswordPolicyError,
    PasswordService,
    validate_password_characters,
)
from tests.email_helpers import (
    FakeSender,
    bearer,
    code_for,
    login_flow,
    post_verify,
    register_flow,
)
from tests.helpers_results import build_match, make_token, make_user

INVISIBLE = "\u200b"
BIDI = "\u202e"


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


# -- nome do jogador ---------------------------------------------------------


def test_canonical_display_name_uppercases_and_collapses_spaces() -> None:
    assert canonicalize_display_name("  joão   da  silva ") == "JOÃO DA SILVA"
    assert canonicalize_display_name("ana-maria_2.0") == "ANA-MARIA_2.0"
    assert canonicalize_display_name("  ") is None
    assert canonicalize_display_name(None) is None


def test_canonical_display_name_rejects_emoji_cjk_and_arabic() -> None:
    for value in ("Ad🎾", "日本語", "لاعب", "ΔΗΜΗΤΡΗΣ"):
        with pytest.raises(InvalidDisplayNameChars):
            canonicalize_display_name(value)


def test_canonical_display_name_enforces_3_to_60() -> None:
    for value in ("A", "É", "a" * 61):
        with pytest.raises(InvalidDisplayNameLength):
            canonicalize_display_name(value)
    assert canonicalize_display_name("Ana") == "ANA"


def test_profile_display_name_http_policy(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    headers = bearer(make_token(db_session, user_id))

    cases = (
        ("João 🎾", "invalid_display_name_chars"),
        ("日本語", "invalid_display_name_chars"),
        ("لاعب", "invalid_display_name_chars"),
        ("A", "invalid_display_name_length"),
        ("a" * 61, "invalid_display_name_length"),
        (f"Ad{INVISIBLE}min", "validation_error"),
        (f"Ad{BIDI}min", "validation_error"),
    )
    for value, code in cases:
        response = api.put("/api/v1/me/profile", headers=headers, json={"display_name": value})
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == code, response.text

    accepted = api.put(
        "/api/v1/me/profile",
        headers=headers,
        json={"display_name": "  joão   da  silva "},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["display_name"] == "JOÃO DA SILVA"


def test_registration_and_admin_reuse_display_name_policy() -> None:
    with pytest.raises(ValidationError):
        email_auth.EmailRegisterRequest(
            challenge_id=uuid.uuid4(),
            email="jogador@example.com",
            password="SenhaSeguraBeta123",
            display_name="Jogador 🎾",
        )
    with pytest.raises(ValidationError):
        profile_api.ProfileUpdateRequest(display_name="日本語")


def test_registration_http_rejects_emoji_display_name(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    email = "emoji-nome@example.com"
    issued, code = code_for(email_api, db_session, sender, email, "registration")
    verified = post_verify(email_api, issued["challenge_id"], code)
    assert verified.status_code == 200, verified.text
    response = email_api.post(
        "/api/v1/auth/email/register",
        json={
            "challenge_id": verified.json()["challenge_id"],
            "email": email,
            "password": "SenhaSeguraBeta123",
            "display_name": "Jogador 🎾",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_display_name_chars"


# -- nome de clã, organização e quadra ---------------------------------------


def test_clan_name_rejects_emoji_and_respects_limits() -> None:
    assert canonicalize_clan_name("  Clã   Tijuca ") == "Clã Tijuca"
    for value in ("Clã 🏐", "日本語", "Clã \ufffd"):
        with pytest.raises((InvalidNameChars, InvalidNameLength)):
            canonicalize_clan_name(value)
    for value in ("A", "a" * 41):
        with pytest.raises(InvalidNameLength):
            canonicalize_clan_name(value)


def test_clan_and_venue_schemas_reject_emoji_in_names() -> None:
    with pytest.raises(ValidationError):
        clans.ClanCreateRequest(name="Clã 🏐", tag="TFC")
    with pytest.raises(ValidationError):
        organizations.OrganizationCreate(name="Arena 🏟️", cnpj="11222333000181", cpf="0" * 11)
    with pytest.raises(ValidationError):
        organizations.VenueCreate(name="Quadra 🏐", latitude=-22.9, longitude=-43.2)
    with pytest.raises(ValidationError):
        venues.SpaceCreate(name="Quadra 🏐")


def test_clan_name_http_rejects_emoji(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    headers = bearer(make_token(db_session, user_id))
    response = api.post(
        "/api/v1/clans",
        headers=headers,
        json={"name": "Clã 🏐", "tag": "TFC"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_name_chars"


# -- senha -------------------------------------------------------------------


def test_password_accepts_accent_and_emoji_exactly() -> None:
    for password in ("AçãoSegura123", "Senha🎾Forte123"):
        assert validate_password_characters(password) == password


def test_password_rejects_control_zero_width_and_edge_spaces() -> None:
    for password in ("senha\x00segura123", "senha\x1fsegura123", f"senha{INVISIBLE}segura123"):
        with pytest.raises(InvalidPasswordChars):
            validate_password_characters(password)
    for password in (" SenhaSegura123", "SenhaSegura123 ", "   ", "\tSenhaSegura123"):
        with pytest.raises((InvalidPasswordChars, InvalidPasswordWhitespace)):
            validate_password_characters(password)


def test_password_hash_verify_do_not_trim() -> None:
    service = PasswordService()
    password = "Senha Segura 123"
    digest = service.hash(password)
    assert service.verify(digest, password) is True
    assert service.verify(digest, f" {password}") is False
    assert service.verify(digest, f"{password} ") is False


def test_password_api_returns_422_without_echoing_the_secret(
    email_api: TestClient,
) -> None:
    bad_passwords = ("Senha\x00Segura123", f"Senha{INVISIBLE}Segura123", " SenhaSegura123")
    for index, password in enumerate(bad_passwords):
        response = email_api.post(
            "/api/v1/auth/email/login",
            json={"email": f"naoexiste{index}@example.com", "password": password},
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["code"] in {"invalid_password_chars", "invalid_password_spaces"}
        assert password not in response.text


def test_strong_unicode_password_registers_and_logs_in(
    email_api: TestClient,
    db_session: Session,
) -> None:
    sender = FakeSender()
    email = "unicode-senha@example.com"
    password = "Ação🎾Segura123"
    register_flow(email_api, db_session, sender, email, password=password, display_name="Ana")
    logged = login_flow(email_api, email, password=password)
    assert logged["access_token"]


def test_password_max_length_is_128() -> None:
    service = PasswordService()
    service.validate("a" * PASSWORD_MAX_LENGTH, "jogador@example.com")
    with pytest.raises(PasswordPolicyError):
        service.validate("a" * (PASSWORD_MAX_LENGTH + 1), "jogador@example.com")


# -- texto livre com emoji ---------------------------------------------------


def test_free_text_rejects_invisibles_and_keeps_emoji() -> None:
    assert clans.JoinRequestCreate(message="quero entrar 🏐").message == "quero entrar 🏐"
    with pytest.raises(ValidationError):
        clans.JoinRequestCreate(message=f"quero{INVISIBLE}entrar")
    with pytest.raises(ValidationError):
        clans.ReportCreate(reason=f"ofensa{BIDI}")


def test_chat_and_clan_description_accept_emoji(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    match, users, _, _ = build_match(db_session, checked_in=10)
    token = make_token(db_session, users[0])
    headers = {**bearer(token), "Idempotency-Key": f"policy-chat-{uuid.uuid4()}"}
    message = api.post(
        f"/api/v1/lobbies/{match.lobby_id}/messages",
        headers=headers,
        json={"body": "bom jogo 🎾\nsegunda linha 🏐"},
    )
    assert message.status_code == 201, message.text
    assert message.json()["body"] == "bom jogo 🎾\nsegunda linha 🏐"

    clan_owner = make_user(db_session)
    clan_response = api.post(
        "/api/v1/clans",
        headers=bearer(make_token(db_session, clan_owner)),
        json={"name": "Clã Praia", "tag": "CPR", "description": "Treino de vôlei 🏐"},
    )
    assert clan_response.status_code == 201, clan_response.text
    assert clan_response.json()["description"] == "Treino de vôlei 🏐"
