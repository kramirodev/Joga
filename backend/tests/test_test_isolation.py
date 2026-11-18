"""Garante que a suíte não carrega segredos do ``.env`` real do desenvolvedor."""

from __future__ import annotations

from app.core.config import (
    DEFAULT_PHONE_HASH_SECRET,
    DEFAULT_TOKEN_HASH_SECRET,
    get_settings,
)
from tests.compliance_helpers import TEST_CPF_KEY, TEST_CPF_KEY_ID


def test_hermetic_settings_neutralize_real_environment() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.environment == "test"
    assert settings.email_provider == "none"
    assert settings.auth_email_enabled is False
    assert settings.auth_phone_enabled is True
    assert settings.allow_phone_registration is True
    assert settings.web_cookie_secure is False
    assert settings.dev_fixed_otp is None

    assert settings.phone_hash_secret.get_secret_value() == DEFAULT_PHONE_HASH_SECRET
    assert settings.token_hash_secret.get_secret_value() == DEFAULT_TOKEN_HASH_SECRET

    assert settings.cpf_key is not None
    assert settings.cpf_key.get_secret_value() == TEST_CPF_KEY
    assert settings.cpf_key_id == TEST_CPF_KEY_ID
