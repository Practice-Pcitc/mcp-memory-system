"""Memory lifecycle orchestration across MySQL and Milvus."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Conversation, Memory, User, utc_now
from app.db.session import session_scope
from app.embeddings import EmbeddingProvider
from app.schemas import (
    DeleteMemoryResult,
    MemoryCreate,
    MemoryList,
    MemoryRead,
    MemorySearch,
    MemoryUpdate,
)
from app.vector import VectorStore


class MemoryNotFoundError(LookupError):
    pass


class MemoryService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    @staticmethod
    def _to_read(memory: Memory, score: float | None = None) -> MemoryRead:
        return MemoryRead(
            id=memory.id,
            user_id=memory.user_id,
            conversation_id=memory.conversation_id,
            content=memory.content,
            tags=list(memory.tags or []),
            metadata=dict(memory.metadata_json or {}),
            status=memory.status,
            vector_status=memory.vector_status,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            score=score,
        )

    @staticmethod
    def _require_memory(session: Session, memory_id: str, user_id: str) -> Memory:
        memory = session.get(Memory, memory_id)
        if memory is None or memory.user_id != user_id or memory.status == "deleted":
            raise MemoryNotFoundError(f"memory {memory_id} was not found")
        return memory

    @staticmethod
    def _ensure_owner_records(
        session: Session, user_id: str, conversation_id: str | None
    ) -> None:
        user = session.get(User, user_id)
        if user is None:
            session.add(User(id=user_id))
        else:
            user.updated_at = utc_now()

        if conversation_id:
            conversation = session.get(Conversation, (user_id, conversation_id))
            if conversation is None:
                session.add(Conversation(user_id=user_id, id=conversation_id))
            else:
                conversation.updated_at = utc_now()

    def _mark_vector_failure(self, memory_id: str) -> None:
        with session_scope(self.session_factory) as session:
            memory = session.get(Memory, memory_id)
            if memory:
                memory.status = "failed"
                memory.vector_status = "failed"

    def write_memory(self, payload: MemoryCreate) -> MemoryRead:
        memory_id = str(uuid4())
        created_at = utc_now()
        memory = Memory(
            id=memory_id,
            user_id=payload.user_id,
            conversation_id=payload.conversation_id,
            content=payload.content,
            tags=payload.tags,
            metadata_json=payload.metadata,
            status="syncing",
            vector_status="pending",
            created_at=created_at,
            updated_at=created_at,
        )
        with session_scope(self.session_factory) as session:
            self._ensure_owner_records(
                session, payload.user_id, payload.conversation_id
            )
            session.add(memory)

        try:
            vector = self.embedding_provider.embed([payload.content])[0]
            self.vector_store.upsert(
                memory_id=memory_id,
                user_id=payload.user_id,
                conversation_id=payload.conversation_id,
                created_at=created_at,
                vector=vector,
            )
        except Exception:
            self._mark_vector_failure(memory_id)
            raise

        with session_scope(self.session_factory) as session:
            stored = session.get(Memory, memory_id)
            if stored is None:
                raise MemoryNotFoundError(f"memory {memory_id} disappeared after write")
            stored.status = "active"
            stored.vector_status = "ready"
            stored.updated_at = utc_now()
            session.flush()
            result = self._to_read(stored)
        return result

    def search_memory(self, payload: MemorySearch) -> list[MemoryRead]:
        query_vector = self.embedding_provider.embed([payload.query])[0]
        candidate_limit = min(max(payload.top_k * 5, payload.top_k), 500)
        hits = self.vector_store.search(
            vector=query_vector,
            user_id=payload.user_id,
            top_k=candidate_limit,
            conversation_id=payload.conversation_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if not hits:
            return []

        hit_ids = [hit.memory_id for hit in hits]
        scores = {hit.memory_id: hit.score for hit in hits}
        with session_scope(self.session_factory) as session:
            statement = select(Memory).where(
                Memory.id.in_(hit_ids),
                Memory.user_id == payload.user_id,
                Memory.status == "active",
            )
            if payload.start_time:
                statement = statement.where(Memory.created_at >= payload.start_time)
            if payload.end_time:
                statement = statement.where(Memory.created_at <= payload.end_time)
            rows = session.scalars(statement).all()
            by_id = {memory.id: memory for memory in rows}
            ordered: list[MemoryRead] = []
            for memory_id in hit_ids:
                memory = by_id.get(memory_id)
                if memory is None:
                    continue
                if payload.tags and not all(tag in memory.tags for tag in payload.tags):
                    continue
                ordered.append(self._to_read(memory, scores[memory_id]))
                if len(ordered) >= payload.top_k:
                    break
            return ordered

    def list_memories(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
        conversation_id: str | None = None,
        tags: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MemoryList:
        statement: Select[tuple[Memory]] = select(Memory).where(
            Memory.user_id == user_id,
            Memory.status == "active",
        )
        if conversation_id:
            statement = statement.where(Memory.conversation_id == conversation_id)
        if start_time:
            statement = statement.where(Memory.created_at >= start_time)
        if end_time:
            statement = statement.where(Memory.created_at <= end_time)
        statement = statement.order_by(Memory.created_at.desc())

        with session_scope(self.session_factory) as session:
            rows = list(session.scalars(statement).all())
            normalized_tags = [tag.strip() for tag in tags or [] if tag.strip()]
            if normalized_tags:
                rows = [
                    row
                    for row in rows
                    if all(tag in row.tags for tag in normalized_tags)
                ]
            total = len(rows)
            page = rows[offset : offset + limit]
            return MemoryList(
                items=[self._to_read(memory) for memory in page],
                total=total,
                offset=offset,
                limit=limit,
            )

    def get_memory(self, memory_id: str, user_id: str) -> MemoryRead:
        with session_scope(self.session_factory) as session:
            memory = self._require_memory(session, memory_id, user_id)
            return self._to_read(memory)

    def update_memory(
        self, memory_id: str, user_id: str, payload: MemoryUpdate
    ) -> MemoryRead:
        current = self.get_memory(memory_id, user_id)
        content_changed = payload.content is not None and payload.content != current.content

        if content_changed:
            new_vector = self.embedding_provider.embed([payload.content or ""])[0]
            self.vector_store.upsert(
                memory_id=current.id,
                user_id=current.user_id,
                conversation_id=current.conversation_id,
                created_at=current.created_at,
                vector=new_vector,
            )

        try:
            with session_scope(self.session_factory) as session:
                memory = self._require_memory(session, memory_id, user_id)
                if payload.content is not None:
                    memory.content = payload.content
                if payload.tags is not None:
                    memory.tags = payload.tags
                if payload.metadata is not None:
                    memory.metadata_json = payload.metadata
                memory.status = "active"
                memory.vector_status = "ready"
                memory.updated_at = utc_now()
                session.flush()
                return self._to_read(memory)
        except Exception:
            if content_changed:
                old_vector = self.embedding_provider.embed([current.content])[0]
                self.vector_store.upsert(
                    memory_id=current.id,
                    user_id=current.user_id,
                    conversation_id=current.conversation_id,
                    created_at=current.created_at,
                    vector=old_vector,
                )
            raise

    def delete_memory(self, memory_id: str, user_id: str) -> DeleteMemoryResult:
        self.get_memory(memory_id, user_id)
        self.vector_store.delete(memory_id)
        with session_scope(self.session_factory) as session:
            memory = self._require_memory(session, memory_id, user_id)
            memory.status = "deleted"
            memory.vector_status = "deleted"
            memory.deleted_at = datetime.now(timezone.utc)
            memory.updated_at = utc_now()
        return DeleteMemoryResult(memory_id=memory_id, deleted=True)

