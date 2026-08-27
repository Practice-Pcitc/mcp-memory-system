"""Core business behavior and isolation tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Memory
from app.embeddings import HashEmbeddingProvider
from app.schemas import MemoryCreate, MemorySearch, MemoryUpdate
from app.services import MemoryNotFoundError, MemoryService
from tests.fakes import FailingVectorStore, FakeVectorStore


def test_write_search_and_user_isolation(memory_service: MemoryService) -> None:
    first = memory_service.write_memory(
        MemoryCreate(
            user_id="user-a",
            conversation_id="conversation-1",
            content="用户喜欢 Python 和向量数据库",
            tags=["preference", "python"],
        )
    )
    memory_service.write_memory(
        MemoryCreate(
            user_id="user-b",
            content="用户喜欢 Python 和向量数据库",
            tags=["private"],
        )
    )

    results = memory_service.search_memory(
        MemorySearch(
            user_id="user-a",
            query="用户喜欢 Python 和向量数据库",
            tags=["python"],
        )
    )

    assert [item.id for item in results] == [first.id]
    assert all(item.user_id == "user-a" for item in results)


def test_list_update_and_delete(
    memory_service: MemoryService, fake_vector_store: FakeVectorStore
) -> None:
    created = memory_service.write_memory(
        MemoryCreate(
            user_id="user-a",
            content="旧内容",
            tags=["old"],
            metadata={"source": "test"},
        )
    )

    updated = memory_service.update_memory(
        created.id,
        "user-a",
        MemoryUpdate(content="新内容", tags=["new"]),
    )
    assert updated.content == "新内容"
    assert updated.tags == ["new"]

    listed = memory_service.list_memories("user-a", tags=["new"])
    assert listed.total == 1
    assert listed.items[0].id == created.id

    result = memory_service.delete_memory(created.id, "user-a")
    assert result.deleted is True
    assert created.id not in fake_vector_store.records
    assert memory_service.list_memories("user-a").total == 0
    with pytest.raises(MemoryNotFoundError):
        memory_service.get_memory(created.id, "user-a")


def test_vector_failure_is_recorded(
    session_factory: sessionmaker[Session],
) -> None:
    service = MemoryService(
        session_factory,
        HashEmbeddingProvider(64),
        FailingVectorStore(),
    )

    with pytest.raises(RuntimeError, match="simulated vector failure"):
        service.write_memory(
            MemoryCreate(user_id="user-a", content="无法建立向量的记忆")
        )

    with session_factory() as session:
        memory = session.scalar(select(Memory))
        assert memory is not None
        assert memory.status == "failed"
        assert memory.vector_status == "failed"


def test_cross_user_access_is_rejected(memory_service: MemoryService) -> None:
    created = memory_service.write_memory(
        MemoryCreate(user_id="owner", content="只属于 owner 的内容")
    )

    with pytest.raises(MemoryNotFoundError):
        memory_service.get_memory(created.id, "other-user")

