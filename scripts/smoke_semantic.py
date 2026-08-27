"""End-to-end semantic smoke test using production dependencies."""

import os
from uuid import uuid4

from app.dependencies import get_memory_service
from app.schemas import MemoryCreate, MemorySearch


def main() -> None:
    os.environ["EMBEDDING_LOCAL_FILES_ONLY"] = "true"
    service = get_memory_service()
    user_id = f"semantic-smoke-{uuid4()}"
    created = service.write_memory(
        MemoryCreate(
            user_id=user_id,
            conversation_id="semantic-smoke-conversation",
            content="用户偏好简洁、清晰并且带有可执行步骤的中文技术说明。",
            tags=["semantic-smoke", "preference"],
        )
    )
    results = service.search_memory(
        MemorySearch(
            user_id=user_id,
            query="这个用户喜欢怎样的回答方式？",
            top_k=3,
            tags=["semantic-smoke"],
        )
    )
    assert results and any(item.id == created.id for item in results)
    service.delete_memory(created.id, user_id)
    print("semantic end-to-end smoke test passed")


if __name__ == "__main__":
    main()
