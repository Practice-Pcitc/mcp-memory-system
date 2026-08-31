"""Deterministic vector repository used by unit tests."""

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Any

from app.vector import VectorHit


@dataclass
class StoredVector:
    user_id: str
    conversation_id: str | None
    project_path: str | None
    created_at: datetime
    vector: list[float]


class FakeVectorStore:
    def __init__(self) -> None:
        self.records: dict[str, StoredVector] = {}

    def ensure_collection(self) -> None:
        return None

    def upsert(
        self,
        memory_id: str,
        user_id: str,
        conversation_id: str | None,
        project_path: str | None,
        created_at: datetime,
        vector: list[float],
    ) -> None:
        self.records[memory_id] = StoredVector(
            user_id=user_id,
            conversation_id=conversation_id,
            project_path=project_path,
            created_at=created_at,
            vector=vector,
        )

    def search(
        self,
        vector: list[float],
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        project_path: str | None = None,
        include_global: bool = True,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for memory_id, record in self.records.items():
            if record.user_id != user_id:
                continue
            if conversation_id and record.conversation_id != conversation_id:
                continue
            if project_path is None and record.project_path is not None:
                continue
            if project_path is not None:
                allowed_paths = {project_path, None} if include_global else {project_path}
                if record.project_path not in allowed_paths:
                    continue
            if start_time and record.created_at < start_time:
                continue
            if end_time and record.created_at > end_time:
                continue
            hits.append(VectorHit(memory_id, self._cosine(vector, record.vector)))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    def delete(self, memory_id: str) -> None:
        self.records.pop(memory_id, None)

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left)) or 1.0
        right_norm = sqrt(sum(value * value for value in right)) or 1.0
        return numerator / (left_norm * right_norm)


class FailingVectorStore(FakeVectorStore):
    def upsert(
        self,
        memory_id: str,
        user_id: str,
        conversation_id: str | None,
        project_path: str | None,
        created_at: datetime,
        vector: list[float],
    ) -> None:
        raise RuntimeError("simulated vector failure")


class FakeKeywordStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def ensure_index(self) -> None:
        return None

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
    ) -> None:
        self.records[memory_id] = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "project_path": project_path,
            "content": content,
            "tags": tags,
            "metadata": metadata,
            "created_at": created_at,
            "updated_at": updated_at,
        }

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
    ) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for memory_id, record in self.records.items():
            if record["user_id"] != user_id:
                continue
            if query.lower() not in record["content"].lower():
                continue
            if conversation_id and record["conversation_id"] != conversation_id:
                continue
            allowed = {project_path, None} if project_path and include_global else {project_path}
            if record["project_path"] not in allowed:
                continue
            if tags and not all(tag in record["tags"] for tag in tags):
                continue
            if start_time and record["created_at"] < start_time:
                continue
            if end_time and record["created_at"] > end_time:
                continue
            hits.append(VectorHit(memory_id, 1.0))
        return hits[:top_k]

    def delete(self, memory_id: str) -> None:
        self.records.pop(memory_id, None)
