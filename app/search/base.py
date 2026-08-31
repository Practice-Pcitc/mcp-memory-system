"""Keyword search contract shared by Elasticsearch and tests."""

from datetime import datetime
from typing import Any, Protocol

from app.vector import VectorHit


class KeywordStore(Protocol):
    def ensure_index(self) -> None: ...

    def upsert(
        self,
        memory_id: str,
        user_id: str,
        conversation_id: str | None,
        project_path: str | None,
        content: str,
        tags: list[str],
        metadata: dict[str, Any],
        created_at: datetime,
        updated_at: datetime,
    ) -> None: ...

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        project_path: str | None = None,
        include_global: bool = True,
        tags: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[VectorHit]: ...

    def delete(self, memory_id: str) -> None: ...
