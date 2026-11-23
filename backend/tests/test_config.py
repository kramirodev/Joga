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
        "web_cookie_secure": True,
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


def test_session_ttl_defaults_keep_the_app_logged_in(monkeypatch) -> None:
    """ADR 0059: inatividade de 30 dias e vida absoluta de 180 dias."""
    for name in (
        "JOGA_ACCESS_TOKEN_TTL_SECONDS",
        "JOGA_REFRESH_ABSOLUTE_TTL_DAYS",
        "JOGA_REFRESH_IDLE_TTL_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    assert settings.access_token_ttl_seconds == 600
    assert settings.refresh_idle_ttl_days == 30
    assert settings.refresh_absolute_ttl_days == 180


def test_production_rejects_default_phone_hash_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", web_cookie_secure=True)

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            phone_hash_secret="real-secret-outside-the-repository",
            web_cookie_secure=True,
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


def test_demo_rejects_insecure_web_cookie() -> None:
    with pytest.raises(ValidationError, match="JOGA_WEB_COOKIE_SECURE"):
        demo_settings(web_cookie_secure=False)


def test_demo_accepts_secure_web_cookie() -> None:
    settings = demo_settings(web_cookie_secure=True)

    assert settings.web_cookie_secure is True


def test_production_rejects_insecure_web_cookie() -> None:
    with pytest.raises(ValidationError, match="JOGA_WEB_COOKIE_SECURE"):
        Settings(
            _env_file=None,
            environment="production",
            phone_hash_secret="real-secret-outside-the-repository",
            token_hash_secret="real-token-secret-outside-the-repository",
            **production_psp_kwargs(web_cookie_secure=False),
        )


def test_local_allows_insecure_web_cookie() -> None:
    settings = Settings(_env_file=None, environment="local", web_cookie_secure=False)

    assert settings.web_cookie_secure is False


def test_database_check_runs_trivial_query() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    database = Database(engine)

    database.check()
    database.dispose()


def test_push_defaults_use_expo_and_optional_token() -> None:
    settings = Settings(_env_file=None)

    assert settings.expo_push_url == "https://exp.host/--/api/v2/push/send"
    assert settings.expo_access_token.get_secret_value() == ""
    assert settings.expo_access_token_value is None
    assert settings.push_timeout_seconds == 5
    assert settings.notification_dispatch_interval_seconds == 5


def test_expo_push_url_requires_https() -> None:
    with pytest.raises(ValidationError, match="JOGA_EXPO_PUSH_URL"):
        Settings(_env_file=None, expo_push_url="http://exp.host/--/api/v2/push/send")


def test_blank_expo_push_url_disables_push_without_breaking_boot() -> None:
    settings = Settings(_env_file=None, expo_push_url="")

    assert settings.expo_push_url is None


def test_notification_dispatch_interval_has_minimum() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_dispatch_interval_seconds=0)
