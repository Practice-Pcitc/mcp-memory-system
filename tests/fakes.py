"""Deterministic vector repository used by unit tests."""

from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from app.vector import VectorHit


@dataclass
class StoredVector:
    user_id: str
    conversation_id: str | None
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
        created_at: datetime,
        vector: list[float],
    ) -> None:
        self.records[memory_id] = StoredVector(
            user_id=user_id,
            conversation_id=conversation_id,
            created_at=created_at,
            vector=vector,
        )

    def search(
        self,
        vector: list[float],
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for memory_id, record in self.records.items():
            if record.user_id != user_id:
                continue
            if conversation_id and record.conversation_id != conversation_id:
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
        created_at: datetime,
        vector: list[float],
    ) -> None:
        raise RuntimeError("simulated vector failure")

