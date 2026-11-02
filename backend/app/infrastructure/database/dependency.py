"""Dependência FastAPI para a engine de banco."""

from functools import lru_cache

from app.core.config import get_settings
from app.infrastructure.database.engine import Database, build_engine


@lru_cache
def get_database() -> Database:
    return Database(build_engine(get_settings()))
