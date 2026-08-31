"""Rebuild the Elasticsearch inverted index from active MySQL memories."""

from sqlalchemy import select

from app.db import get_session_factory, init_database
from app.db.models import Memory
from app.dependencies import get_keyword_store


def main() -> None:
    init_database()
    keyword_store = get_keyword_store()
    if keyword_store is None:
        raise SystemExit(
            "Elasticsearch is disabled. Set ELASTICSEARCH_ENABLED=true in .env first."
        )

    indexed = 0
    with get_session_factory()() as session:
        memories = session.scalars(
            select(Memory).where(Memory.status == "active")
        ).all()
        for memory in memories:
            keyword_store.upsert(
                memory_id=memory.id,
                user_id=memory.user_id,
                conversation_id=memory.conversation_id,
                project_path=memory.project_path,
                content=memory.content,
                tags=list(memory.tags or []),
                metadata=dict(memory.metadata_json or {}),
                created_at=memory.created_at,
                updated_at=memory.updated_at,
            )
            indexed += 1
    print(f"Elasticsearch reindex complete: {indexed} memories")


if __name__ == "__main__":
    main()
