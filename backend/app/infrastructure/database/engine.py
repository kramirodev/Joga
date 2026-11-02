"""Engine e verificação de disponibilidade do PostgreSQL."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class Database:
    """Encapsula a engine para permitir substituição em testes."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> None:
        """Executa uma consulta trivial; levanta exceção se o banco não responder."""
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self._engine.dispose()


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )
