"""Core business behavior and isolation tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Memory
from app.embeddings import HashEmbeddingProvider
from app.schemas import MemoryCreate, MemorySearch, MemoryUpdate
from app.services import MemoryNotFoundError, MemoryService
from tests.fakes import FailingVectorStore, FakeKeywordStore, FakeVectorStore


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


def test_global_and_project_memory_scopes(memory_service: MemoryService) -> None:
    global_memory = memory_service.write_memory(
        MemoryCreate(user_id="user-a", content="全局偏好", project_path=None)
    )
    project_a = memory_service.write_memory(
        MemoryCreate(
            user_id="user-a",
            content="项目 A 约定",
            project_path="D:\\Work\\Project-A\\",
        )
    )
    project_b = memory_service.write_memory(
        MemoryCreate(
            user_id="user-a",
            content="项目 B 约定",
            project_path=r"D:\Work\Project-B",
        )
    )

    assert project_a.project_path == "d:/work/project-a"

    global_results = memory_service.search_memory(
        MemorySearch(user_id="user-a", query="约定和偏好", top_k=10)
    )
    assert {item.id for item in global_results} == {global_memory.id}

    project_results = memory_service.search_memory(
        MemorySearch(
            user_id="user-a",
            query="约定和偏好",
            top_k=10,
            project_path=r"D:\Work\Project-A",
        )
    )
    assert {item.id for item in project_results} == {global_memory.id, project_a.id}
    assert project_b.id not in {item.id for item in project_results}

    project_only = memory_service.list_memories(
        "user-a",
        project_path=r"D:\Work\Project-A",
        include_global=False,
    )
    assert [item.id for item in project_only.items] == [project_a.id]

    moved = memory_service.update_memory(
        global_memory.id,
        "user-a",
        MemoryUpdate(project_path=r"D:\Work\Project-A"),
    )
    assert moved.project_path == "d:/work/project-a"


def test_keyword_and_hybrid_search_lifecycle(
    session_factory: sessionmaker[Session],
    fake_vector_store: FakeVectorStore,
) -> None:
    keyword_store = FakeKeywordStore()
    service = MemoryService(
        session_factory,
        HashEmbeddingProvider(64),
        fake_vector_store,
        keyword_store,
    )
    created = service.write_memory(
        MemoryCreate(
            user_id="user-a",
            content="Elasticsearch 提供倒排索引",
            project_path=r"D:\Work\Project-A",
            tags=["search"],
        )
    )

    keyword_results = service.search_memory(
        MemorySearch(
            user_id="user-a",
            query="Elasticsearch",
            search_mode="keyword",
            project_path=r"D:\Work\Project-A",
        )
    )
    hybrid_results = service.search_memory(
        MemorySearch(
            user_id="user-a",
            query="Elasticsearch",
            search_mode="hybrid",
            project_path=r"D:\Work\Project-A",
        )
    )
    assert [item.id for item in keyword_results] == [created.id]
    assert [item.id for item in hybrid_results] == [created.id]

    service.update_memory(
        created.id,
        "user-a",
        MemoryUpdate(content="关键词检索已更新"),
    )
    assert keyword_store.records[created.id]["content"] == "关键词检索已更新"

    service.delete_memory(created.id, "user-a")
    assert created.id not in keyword_store.records
