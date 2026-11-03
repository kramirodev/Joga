"""Testes de normalização de telefone e hashes HMAC."""

import uuid

import pytest

from app.modules.identity.phone import (
    InvalidPhoneNumber,
    hash_ip,
    hash_otp,
    hash_phone,
    normalize_phone,
)


def test_normalize_accepts_e164_and_strips_formatting() -> None:
    assert normalize_phone(" +55 (11) 98765-4321 ") == "+5511987654321"


@pytest.mark.parametrize(
    "value",
    [
        "11987654321",
        "+55 11 98765-432A",
        "+0123456789",
        "+123",
        "+1234567890123456",
        "",
    ],
)
def test_normalize_rejects_invalid_numbers(value: str) -> None:
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(value)


def test_hash_phone_is_deterministic_and_depends_on_secret() -> None:
    phone = "+5511987654321"

    first = hash_phone(phone, "secret-a")
    second = hash_phone(phone, "secret-a")
    other = hash_phone(phone, "secret-b")

    assert first == second
    assert first != other
    assert phone not in first
    assert len(first) == 64


def test_hash_ip_normalizes_case_and_spaces() -> None:
    assert hash_ip(" 2001:DB8::1 ", "secret") == hash_ip("2001:db8::1", "secret")


def test_hash_otp_is_bound_to_challenge_and_code() -> None:
    challenge_id = uuid.uuid4()
    other_id = uuid.uuid4()

    digest = hash_otp(challenge_id, "123456", "secret")

    assert digest == hash_otp(challenge_id, "123456", "secret")
    assert digest != hash_otp(other_id, "123456", "secret")
    assert digest != hash_otp(challenge_id, "654321", "secret")
    assert "123456" not in digest
