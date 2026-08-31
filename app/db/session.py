"""SQLAlchemy engine and session helpers."""

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.base import Base


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.mysql_url, pool_pre_ping=True, future=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)


def init_database(engine: Engine | None = None) -> None:
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)

    inspector = inspect(target_engine)
    columns = {column["name"] for column in inspector.get_columns("memories")}
    with target_engine.begin() as connection:
        if "project_path" not in columns:
            connection.execute(
                text("ALTER TABLE memories ADD COLUMN project_path VARCHAR(1024) NULL")
            )

    inspector = inspect(target_engine)
    indexes = {index["name"] for index in inspector.get_indexes("memories")}
    if "idx_memories_user_project_status" not in indexes:
        with target_engine.begin() as connection:
            if target_engine.dialect.name == "mysql":
                ddl = (
                    "CREATE INDEX idx_memories_user_project_status "
                    "ON memories (user_id, project_path(191), status)"
                )
            else:
                ddl = (
                    "CREATE INDEX idx_memories_user_project_status "
                    "ON memories (user_id, project_path, status)"
                )
            connection.execute(text(ddl))


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
