"""Testes de configuração e da verificação de banco."""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from app.core.config import DEFAULT_PHONE_HASH_SECRET, Settings
from app.infrastructure.database.engine import Database


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
        )


def test_database_check_runs_trivial_query() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    database = Database(engine)

    database.check()
    database.dispose()
