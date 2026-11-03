"""Dependências FastAPI para engine e sessão de banco."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.infrastructure.database.engine import Database, build_engine


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings())


@lru_cache
def get_database() -> Database:
    return Database(get_engine())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
