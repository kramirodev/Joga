"""Testes de configuração e da verificação de banco."""

from datetime import date

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine

from app.core.config import DEFAULT_PHONE_HASH_SECRET, DEFAULT_TOKEN_HASH_SECRET, Settings
from app.core.environments import is_demo, is_local, is_production
from app.infrastructure.database.engine import Database
from app.modules.payments.adapter import SimulatorPspAdapter, build_psp_adapter
from tests.compliance_helpers import cpf_key_kwargs
from tests.settings_helpers import demo_settings


def production_psp_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "psp_provider": "mercadopago",
        "mercado_pago_access_token": SecretStr("mp-access-token"),
        "mercado_pago_webhook_secret": SecretStr("mp-webhook-secret"),
        "mercado_pago_notification_url": "https://api.joga.example/payments/mercadopago/webhook",
        **cpf_key_kwargs(),
    }
    values.update(overrides)
    return values


def test_settings_use_joga_prefix(monkeypatch) -> None:
    monkeypatch.setenv("JOGA_DATABASE_URL", "postgresql+psycopg://user:pass@example:5432/db")
    monkeypatch.setenv("JOGA_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@example:5432/db"
    assert settings.log_level == "DEBUG"


def test_identity_settings_have_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.otp_ttl_seconds == 300
    assert settings.otp_max_attempts == 5
    assert settings.otp_resend_cooldown_seconds == 60
    assert settings.otp_max_per_hour == 5
    assert settings.phone_hash_secret.get_secret_value() == DEFAULT_PHONE_HASH_SECRET


def test_production_rejects_default_phone_hash_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            phone_hash_secret="real-secret-outside-the-repository",
        )

    settings = Settings(
        _env_file=None,
        environment="production",
        phone_hash_secret="real-secret-outside-the-repository",
        token_hash_secret="real-token-secret-outside-the-repository",
        **production_psp_kwargs(),
    )
    assert settings.environment == "production"


def test_production_rejects_fixed_development_otp() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            phone_hash_secret="real-secret-outside-the-repository",
            token_hash_secret="real-token-secret-outside-the-repository",
            dev_fixed_otp="123456",
            **production_psp_kwargs(),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"psp_provider": "simulator"},
        {"mercado_pago_access_token": None},
        {"mercado_pago_webhook_secret": None},
        {"mercado_pago_notification_url": None},
        {"mercado_pago_notification_url": "http://insecure.example/webhook"},
    ],
)
def test_production_requires_complete_mercadopago_configuration(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            phone_hash_secret="real-secret-outside-the-repository",
            token_hash_secret="real-token-secret-outside-the-repository",
            **production_psp_kwargs(**overrides),
        )


def test_local_keeps_simulator_default_without_webhook_secret() -> None:
    settings = Settings(_env_file=None, environment="local")

    assert settings.psp_provider == "simulator"
    assert settings.mercado_pago_webhook_secret is None


def test_environment_helpers_classify_local_demo_and_production() -> None:
    assert is_local("local")
    assert is_local("test")
    assert is_local("development")
    assert is_local("ci")
    assert is_demo("demo")
    assert is_production("production")
    assert is_production("staging")
    assert not is_production("demo")
    assert not is_production("local")


def test_demo_boots_with_simulator_without_mercadopago() -> None:
    settings = demo_settings()

    assert settings.environment == "demo"
    assert settings.psp_provider == "simulator"
    assert settings.money_mode == "simulated"
    assert settings.ticket_purchase_enabled is False
    assert settings.mercado_pago_access_token is None
    assert settings.mercado_pago_webhook_secret is None
    assert settings.mercado_pago_notification_url is None
    assert isinstance(build_psp_adapter(settings), SimulatorPspAdapter)


def test_demo_rejects_ticket_purchase() -> None:
    with pytest.raises(ValidationError):
        demo_settings(ticket_purchase_enabled=True)


def test_demo_rejects_mercadopago() -> None:
    with pytest.raises(ValidationError):
        demo_settings(
            psp_provider="mercadopago",
            mercado_pago_access_token=SecretStr("mp-access-token"),
        )


def test_demo_rejects_real_money_mode() -> None:
    with pytest.raises(ValidationError):
        demo_settings(
            money_mode="real",
            legal_approval_ref="parecer",
            legal_approval_sha256="a" * 64,
            legal_approval_date=date.today(),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"phone_hash_secret": DEFAULT_PHONE_HASH_SECRET},
        {"token_hash_secret": DEFAULT_TOKEN_HASH_SECRET},
    ],
)
def test_demo_rejects_default_hash_secrets(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        demo_settings(**overrides)


def test_demo_rejects_fixed_development_otp() -> None:
    with pytest.raises(ValidationError):
        demo_settings(dev_fixed_otp="123456")


def test_demo_requires_cpf_key() -> None:
    with pytest.raises(ValidationError):
        demo_settings(cpf_key=None, cpf_key_id=None)


def test_database_check_runs_trivial_query() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    database = Database(engine)

    database.check()
    database.dispose()
