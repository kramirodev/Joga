"""Configuração da API, lida de variáveis de ambiente com prefixo JOGA_."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração explícita; nenhum segredo real tem valor padrão versionado."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOGA_",
        extra="ignore",
    )

    environment: str = "local"
    database_url: str = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
