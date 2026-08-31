"""Elasticsearch-backed inverted index for keyword retrieval."""

from datetime import datetime
from typing import Any

from app.vector import VectorHit


class ElasticsearchKeywordStore:
    def __init__(self, url: str, index_name: str) -> None:
        from elasticsearch import Elasticsearch

        self.index_name = index_name
        self.client = Elasticsearch(url)

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            return
        self.client.indices.create(
            index=self.index_name,
            mappings={
                "dynamic": "strict",
                "properties": {
                    "user_id": {"type": "keyword"},
                    "conversation_id": {"type": "keyword"},
                    "project_path": {"type": "keyword"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "tags": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": False},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                },
            },
        )

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
        document = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "project_path": project_path,
            "content": content,
            "tags": tags,
            "metadata": metadata,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
        }
        self.client.index(
            index=self.index_name,
            id=memory_id,
            document=document,
            refresh="wait_for",
        )

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
        filters: list[dict[str, Any]] = [{"term": {"user_id": user_id}}]
        if conversation_id:
            filters.append({"term": {"conversation_id": conversation_id}})
        for tag in tags or []:
            filters.append({"term": {"tags": tag}})
        if start_time or end_time:
            date_range: dict[str, str] = {}
            if start_time:
                date_range["gte"] = start_time.isoformat()
            if end_time:
                date_range["lte"] = end_time.isoformat()
            filters.append({"range": {"created_at": date_range}})

        global_scope = {"bool": {"must_not": {"exists": {"field": "project_path"}}}}
        if project_path is None:
            filters.append(global_scope)
        elif include_global:
            filters.append(
                {
                    "bool": {
                        "minimum_should_match": 1,
                        "should": [
                            {"term": {"project_path": project_path}},
                            global_scope,
                        ],
                    }
                }
            )
        else:
            filters.append({"term": {"project_path": project_path}})

        response = self.client.search(
            index=self.index_name,
            size=top_k,
            query={
                "bool": {
                    "must": [{"match": {"content": {"query": query}}}],
                    "filter": filters,
                }
            },
            source=False,
        )
        return [
            VectorHit(memory_id=str(hit["_id"]), score=float(hit["_score"] or 0.0))
            for hit in response["hits"]["hits"]
        ]

    def delete(self, memory_id: str) -> None:
        self.client.options(ignore_status=404).delete(
            index=self.index_name,
            id=memory_id,
            refresh="wait_for",
        )
