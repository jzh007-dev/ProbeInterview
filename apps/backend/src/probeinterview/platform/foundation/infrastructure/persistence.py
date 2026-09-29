"""Shared SQLAlchemy engine, metadata, and session construction."""

from sqlalchemy import Engine
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative metadata shared by module-owned ORM mappings."""


def create_engine(database_url: str) -> Engine:
    """Create the PostgreSQL engine used by API, worker, migrations, and tools."""

    return sqlalchemy_create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions with explicit transaction ownership at the caller."""

    return sessionmaker(bind=engine, expire_on_commit=False)
