"""Combinações de flags de fase e validação de boot (ADR 0050)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def local_email_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "local",
        "auth_email_enabled": True,
        "auth_phone_enabled": False,
        "allow_phone_registration": False,
        "allow_email_registration": True,
        "phone_required_for_booking": False,
        "email_provider": "fake",
        "email_from": "no-reply@joga.example",
        "email_from_name": "JOGA",
        "email_api_key": SecretStr("test-key"),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def production_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": "production",
        "phone_hash_secret": "real-identity-secret",
        "token_hash_secret": "real-token-secret",
        "psp_provider": "mercadopago",
        "mercado_pago_access_token": SecretStr("mp-token"),
        "mercado_pago_webhook_secret": SecretStr("mp-webhook"),
        "mercado_pago_notification_url": "https://api.joga.example/webhook",
        "auth_email_enabled": False,
        "auth_phone_enabled": True,
    }
    values.update(overrides)
    return values


def test_beta_profile_is_valid() -> None:
    settings = local_email_settings()
    assert settings.auth_email_enabled and not settings.auth_phone_enabled
    assert settings.phone_required_for_booking is False
    assert settings.signup_mode == "open"
    assert settings.email_max_per_ip_per_hour == 50
    assert settings.signup_max_per_ip_per_day == 20


def test_launch_profile_is_valid() -> None:
    settings = local_email_settings(
        auth_phone_enabled=True,
        allow_phone_registration=True,
        phone_required_for_booking=True,
        email_daily_budget=200,
    )
    assert settings.auth_email_enabled and settings.auth_phone_enabled
    assert settings.phone_required_for_booking is True


def test_defaults_preserve_phone_path() -> None:
    settings = Settings(_env_file=None)
    assert settings.auth_phone_enabled is True
    assert settings.auth_email_enabled is False
    assert settings.email_provider == "none"


def test_no_enabled_credential_fails() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(auth_email_enabled=False, auth_phone_enabled=False)


def test_phone_disabled_cannot_keep_phone_registration() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(allow_phone_registration=True)


def test_phone_disabled_cannot_require_phone_for_booking() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(phone_required_for_booking=True)


def test_email_enabled_requires_provider() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(email_provider="none")


def test_provider_requires_key_and_from() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(email_provider="brevo", email_api_key=None)
    with pytest.raises(ValidationError):
        local_email_settings(email_provider="brevo", email_from=None)
    with pytest.raises(ValidationError):
        local_email_settings(email_provider="brevo", email_from_name=" ")


def test_invalid_from_rejected() -> None:
    with pytest.raises(ValidationError):
        local_email_settings(email_from="nao-e-email")


def test_fake_provider_rejected_outside_local() -> None:
    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            **production_kwargs(
                auth_email_enabled=True,
                auth_phone_enabled=False,
                allow_phone_registration=False,
                email_provider="fake",
                email_from="no-reply@joga.example",
                email_api_key=SecretStr("key"),
            ),
        )


@pytest.mark.parametrize("budget", [0, 300, 301])
def test_budget_must_be_positive_and_below_brevo_quota(budget: int) -> None:
    with pytest.raises(ValidationError):
        local_email_settings(
            email_provider="brevo",
            email_api_key=SecretStr("key"),
            email_from="no-reply@joga.example",
            email_daily_budget=budget,
        )


def test_budget_just_below_quota_is_valid() -> None:
    settings = local_email_settings(
        email_provider="brevo",
        email_api_key=SecretStr("key"),
        email_from="no-reply@joga.example",
        email_daily_budget=299,
    )
    assert settings.email_daily_budget == 299


def test_fake_provider_ignores_paid_quota() -> None:
    settings = local_email_settings(email_provider="fake", email_daily_budget=5_000)
    assert settings.email_daily_budget == 5_000
