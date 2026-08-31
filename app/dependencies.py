"""Cached construction of production service dependencies."""

from functools import lru_cache

from app.config import get_settings
from app.db import get_session_factory, init_database
from app.embeddings import EmbeddingProvider, build_embedding_provider
from app.search import ElasticsearchKeywordStore, KeywordStore
from app.services import MemoryService
from app.vector import MilvusVectorStore


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())


@lru_cache
def get_vector_store() -> MilvusVectorStore:
    settings = get_settings()
    store = MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_collection,
        settings.embedding_dimension,
    )
    store.ensure_collection()
    return store


@lru_cache
def get_keyword_store() -> KeywordStore | None:
    settings = get_settings()
    if not settings.elasticsearch_enabled:
        return None
    store = ElasticsearchKeywordStore(
        settings.elasticsearch_url,
        settings.elasticsearch_index,
    )
    store.ensure_index()
    return store


@lru_cache
def get_memory_service() -> MemoryService:
    init_database()
    return MemoryService(
        get_session_factory(),
        get_embedding_provider(),
        get_vector_store(),
        get_keyword_store(),
    )
