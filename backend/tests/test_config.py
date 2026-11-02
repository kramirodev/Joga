"""Testes de configuração e da verificação de banco."""

from sqlalchemy import create_engine

from app.core.config import Settings
from app.infrastructure.database.engine import Database


def test_settings_use_joga_prefix(monkeypatch) -> None:
    monkeypatch.setenv("JOGA_DATABASE_URL", "postgresql+psycopg://user:pass@example:5432/db")
    monkeypatch.setenv("JOGA_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@example:5432/db"
    assert settings.log_level == "DEBUG"


def test_database_check_runs_trivial_query() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    database = Database(engine)

    database.check()
    database.dispose()
