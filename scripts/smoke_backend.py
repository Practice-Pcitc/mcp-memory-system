"""Exercise the core service against local MySQL and Milvus."""

from app.config import Settings
from app.db import get_session_factory, init_database
from app.embeddings import HashEmbeddingProvider
from app.schemas import MemoryCreate, MemorySearch, MemoryUpdate
from app.services import MemoryService
from app.vector import MilvusVectorStore


def main() -> None:
    settings = Settings(embedding_provider="hash")
    init_database()
    vector_store = MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_collection,
        settings.embedding_dimension,
    )
    vector_store.ensure_collection()
    service = MemoryService(
        get_session_factory(),
        HashEmbeddingProvider(settings.embedding_dimension),
        vector_store,
    )

    created = service.write_memory(
        MemoryCreate(
            user_id="smoke-user",
            conversation_id="smoke-conversation",
            content="我喜欢使用 Python 构建长期记忆系统",
            tags=["smoke", "python"],
        )
    )
    results = service.search_memory(
        MemorySearch(
            user_id="smoke-user",
            query="Python 长期记忆系统",
            top_k=5,
            tags=["smoke"],
        )
    )
    assert any(item.id == created.id for item in results)

    updated = service.update_memory(
        created.id,
        "smoke-user",
        MemoryUpdate(content="我正在实现 Python MCP 长期记忆系统"),
    )
    assert updated.content.startswith("我正在实现")

    deleted = service.delete_memory(created.id, "smoke-user")
    assert deleted.deleted
    assert not service.search_memory(
        MemorySearch(user_id="smoke-user", query="Python MCP", top_k=5)
    )
    print("backend smoke test passed")


if __name__ == "__main__":
    main()

