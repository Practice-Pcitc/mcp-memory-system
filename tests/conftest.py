"""Shared isolated test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.embeddings import HashEmbeddingProvider
from app.services import MemoryService
from tests.fakes import FakeVectorStore


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    yield factory
    engine.dispose()


@pytest.fixture
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def memory_service(
    session_factory: sessionmaker[Session],
    fake_vector_store: FakeVectorStore,
) -> MemoryService:
    return MemoryService(
        session_factory,
        HashEmbeddingProvider(64),
        fake_vector_store,
    )

