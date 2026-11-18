"""Normalização e hash de e-mail (sem rede)."""

from __future__ import annotations

import pytest

from app.modules.email.addresses import (
    BUILTIN_DISPOSABLE_DOMAINS,
    InvalidEmail,
    email_domain,
    hash_email,
    is_disposable_domain,
    normalize_email,
)


def test_normalize_trims_lowercases_and_keeps_local_part() -> None:
    assert normalize_email("  Jogador.Teste+1@Example.COM  ") == "jogador.teste+1@example.com"


def test_normalize_converts_domain_to_punycode() -> None:
    normalized = normalize_email("jogador@joão.com")
    assert normalized.startswith("jogador@xn--")
    assert normalized.endswith(".com")
    assert "ã" not in normalized


def test_normalize_does_not_merge_dots_or_plus_aliases() -> None:
    assert normalize_email("a.b@gmail.com") != normalize_email("ab@gmail.com")
    assert normalize_email("a+1@gmail.com") != normalize_email("a@gmail.com")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sem-arroba",
        "a@@b.com",
        "a b@example.com",
        ".a@example.com",
        "a.@example.com",
        "a..b@example.com",
        "a@localhost",
        "a@127.0.0.1",
        "a@exa_mple.com",
        "a@" + "x" * 250 + ".com",
        ("x" * 65) + "@example.com",
    ],
)
def test_normalize_rejects_invalid_addresses(value: str) -> None:
    with pytest.raises(InvalidEmail):
        normalize_email(value)


def test_domain_and_hash_do_not_expose_address() -> None:
    normalized = "jogador@example.com"
    digest = hash_email(normalized, "secret")
    assert email_domain(normalized) == "example.com"
    assert len(digest) == 64
    assert normalized not in digest
    assert digest == hash_email(normalized, "secret")
    assert digest != hash_email(normalized, "other-secret")


def test_disposable_domain_uses_builtin_and_extra_lists() -> None:
    assert is_disposable_domain("a@mailinator.com", frozenset())
    assert is_disposable_domain("a@sub.mailinator.com", frozenset())
    assert "mailinator.com" in BUILTIN_DISPOSABLE_DOMAINS
    assert is_disposable_domain("a@descartavel.example", frozenset({"descartavel.example"}))
    assert not is_disposable_domain("a@example.com", frozenset({"descartavel.example"}))
