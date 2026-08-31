"""Memory lifecycle orchestration across MySQL and Milvus."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, or_, select
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
from app.search import KeywordStore
from app.vector import VectorStore
from app.vector.milvus_store import VectorHit


class MemoryNotFoundError(LookupError):
    pass


class MemoryService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        keyword_store: KeywordStore | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.keyword_store = keyword_store

    @staticmethod
    def _to_read(memory: Memory, score: float | None = None) -> MemoryRead:
        return MemoryRead(
            id=memory.id,
            user_id=memory.user_id,
            conversation_id=memory.conversation_id,
            project_path=memory.project_path,
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
            project_path=payload.project_path,
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
                project_path=payload.project_path,
                created_at=created_at,
                vector=vector,
            )
            if self.keyword_store is not None:
                self.keyword_store.upsert(
                    memory_id=memory_id,
                    user_id=payload.user_id,
                    conversation_id=payload.conversation_id,
                    project_path=payload.project_path,
                    content=payload.content,
                    tags=payload.tags,
                    metadata=payload.metadata,
                    created_at=created_at,
                    updated_at=created_at,
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
        candidate_limit = min(max(payload.top_k * 5, payload.top_k), 500)
        semantic_hits: list[VectorHit] = []
        keyword_hits: list[VectorHit] = []
        if payload.search_mode in {"semantic", "hybrid"}:
            query_vector = self.embedding_provider.embed([payload.query])[0]
            semantic_hits = self.vector_store.search(
                vector=query_vector,
                user_id=payload.user_id,
                top_k=candidate_limit,
                conversation_id=payload.conversation_id,
                project_path=payload.project_path,
                include_global=payload.include_global,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )
        if payload.search_mode in {"keyword", "hybrid"}:
            if self.keyword_store is None:
                raise RuntimeError(
                    "Elasticsearch keyword search is disabled; set ELASTICSEARCH_ENABLED=true"
                )
            keyword_hits = self.keyword_store.search(
                query=payload.query,
                user_id=payload.user_id,
                top_k=candidate_limit,
                conversation_id=payload.conversation_id,
                project_path=payload.project_path,
                include_global=payload.include_global,
                tags=payload.tags,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )
        hits = self._merge_search_hits(
            semantic_hits, keyword_hits, payload.search_mode
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
            statement = self._apply_project_scope(
                statement, payload.project_path, payload.include_global
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
        project_path: str | None = None,
        include_global: bool = True,
    ) -> MemoryList:
        statement: Select[tuple[Memory]] = select(Memory).where(
            Memory.user_id == user_id,
            Memory.status == "active",
        )
        from app.schemas.memory import normalize_project_path

        normalized_project_path = normalize_project_path(project_path)
        statement = self._apply_project_scope(
            statement, normalized_project_path, include_global
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
        scope_changed = (
            "project_path" in payload.model_fields_set
            and payload.project_path != current.project_path
        )

        if content_changed or scope_changed:
            new_vector = self.embedding_provider.embed([payload.content or ""])[0]
            if not content_changed:
                new_vector = self.embedding_provider.embed([current.content])[0]
            self.vector_store.upsert(
                memory_id=current.id,
                user_id=current.user_id,
                conversation_id=current.conversation_id,
                project_path=payload.project_path if scope_changed else current.project_path,
                created_at=current.created_at,
                vector=new_vector,
            )

        keyword_changed = bool(
            self.keyword_store is not None
            and payload.model_fields_set.intersection(
                {"content", "tags", "metadata", "project_path"}
            )
        )
        if keyword_changed and self.keyword_store is not None:
            self.keyword_store.upsert(
                memory_id=current.id,
                user_id=current.user_id,
                conversation_id=current.conversation_id,
                project_path=(
                    payload.project_path if scope_changed else current.project_path
                ),
                content=payload.content or current.content,
                tags=payload.tags if payload.tags is not None else current.tags,
                metadata=(
                    payload.metadata if payload.metadata is not None else current.metadata
                ),
                created_at=current.created_at,
                updated_at=utc_now(),
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
                if "project_path" in payload.model_fields_set:
                    memory.project_path = payload.project_path
                memory.status = "active"
                memory.vector_status = "ready"
                memory.updated_at = utc_now()
                session.flush()
                return self._to_read(memory)
        except Exception:
            if content_changed or scope_changed:
                old_vector = self.embedding_provider.embed([current.content])[0]
                self.vector_store.upsert(
                    memory_id=current.id,
                    user_id=current.user_id,
                    conversation_id=current.conversation_id,
                    project_path=current.project_path,
                    created_at=current.created_at,
                    vector=old_vector,
                )
            if keyword_changed and self.keyword_store is not None:
                self.keyword_store.upsert(
                    memory_id=current.id,
                    user_id=current.user_id,
                    conversation_id=current.conversation_id,
                    project_path=current.project_path,
                    content=current.content,
                    tags=current.tags,
                    metadata=current.metadata,
                    created_at=current.created_at,
                    updated_at=current.updated_at,
                )
            raise

    @staticmethod
    def _merge_search_hits(
        semantic_hits: list[VectorHit],
        keyword_hits: list[VectorHit],
        search_mode: str,
    ) -> list[VectorHit]:
        if search_mode == "semantic":
            return semantic_hits
        if search_mode == "keyword":
            return keyword_hits

        scores: dict[str, float] = {}
        for hits in (semantic_hits, keyword_hits):
            for rank, hit in enumerate(hits, start=1):
                scores[hit.memory_id] = scores.get(hit.memory_id, 0.0) + 1.0 / (
                    60 + rank
                )
        return [
            VectorHit(memory_id=memory_id, score=score)
            for memory_id, score in sorted(
                scores.items(), key=lambda item: item[1], reverse=True
            )
        ]

    @staticmethod
    def _apply_project_scope(
        statement: Select[tuple[Memory]],
        project_path: str | None,
        include_global: bool,
    ) -> Select[tuple[Memory]]:
        if project_path is None:
            return statement.where(Memory.project_path.is_(None))
        if include_global:
            return statement.where(
                or_(Memory.project_path == project_path, Memory.project_path.is_(None))
            )
        return statement.where(Memory.project_path == project_path)

    def delete_memory(self, memory_id: str, user_id: str) -> DeleteMemoryResult:
        self.get_memory(memory_id, user_id)
        self.vector_store.delete(memory_id)
        if self.keyword_store is not None:
            self.keyword_store.delete(memory_id)
        with session_scope(self.session_factory) as session:
            memory = self._require_memory(session, memory_id, user_id)
            memory.status = "deleted"
            memory.vector_status = "deleted"
            memory.deleted_at = datetime.now(timezone.utc)
            memory.updated_at = utc_now()
        return DeleteMemoryResult(memory_id=memory_id, deleted=True)
