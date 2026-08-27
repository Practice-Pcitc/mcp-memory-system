"""Vector store contract shared by production and test implementations."""

from datetime import datetime
from typing import Protocol

from app.vector.milvus_store import VectorHit


class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert(
        self,
        memory_id: str,
        user_id: str,
        conversation_id: str | None,
        created_at: datetime,
        vector: list[float],
    ) -> None: ...

    def search(
        self,
        vector: list[float],
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[VectorHit]: ...

    def delete(self, memory_id: str) -> None: ...

