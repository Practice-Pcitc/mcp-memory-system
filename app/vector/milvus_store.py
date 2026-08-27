"""Milvus-backed vector index for memory identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pymilvus import DataType, MilvusClient


@dataclass(frozen=True)
class VectorHit:
    memory_id: str
    score: float


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _utc_millis(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


class MilvusVectorStore:
    def __init__(
        self,
        uri: str,
        collection_name: str,
        dimension: int,
        client: MilvusClient | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = client or MilvusClient(uri=uri)

    def ensure_collection(self) -> None:
        if self.client.has_collection(collection_name=self.collection_name):
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=36,
        )
        schema.add_field(
            field_name="user_id",
            datatype=DataType.VARCHAR,
            max_length=128,
        )
        schema.add_field(
            field_name="conversation_id",
            datatype=DataType.VARCHAR,
            max_length=128,
        )
        schema.add_field(field_name="created_at", datatype=DataType.INT64)
        schema.add_field(
            field_name="vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=self.dimension,
        )

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    def upsert(
        self,
        memory_id: str,
        user_id: str,
        conversation_id: str | None,
        created_at: datetime,
        vector: list[float],
    ) -> None:
        if len(vector) != self.dimension:
            raise ValueError(
                f"vector dimension {len(vector)} does not match {self.dimension}"
            )
        timestamp = _utc_millis(created_at)
        self.client.upsert(
            collection_name=self.collection_name,
            data=[
                {
                    "id": memory_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id or "",
                    "created_at": timestamp,
                    "vector": vector,
                }
            ],
        )
        self.client.flush(collection_name=self.collection_name)

    def search(
        self,
        vector: list[float],
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[VectorHit]:
        expressions = [f'user_id == "{_escape_filter_value(user_id)}"']
        if conversation_id:
            escaped_conversation = _escape_filter_value(conversation_id)
            expressions.append(f'conversation_id == "{escaped_conversation}"')
        if start_time:
            start_ms = _utc_millis(start_time)
            expressions.append(f"created_at >= {start_ms}")
        if end_time:
            end_ms = _utc_millis(end_time)
            expressions.append(f"created_at <= {end_ms}")

        results = self.client.search(
            collection_name=self.collection_name,
            data=[vector],
            filter=" and ".join(expressions),
            limit=top_k,
            output_fields=["id"],
            search_params={"metric_type": "COSINE", "params": {}},
        )
        if not results:
            return []
        return [
            VectorHit(memory_id=str(item["id"]), score=float(item["distance"]))
            for item in results[0]
        ]

    def delete(self, memory_id: str) -> None:
        self.client.delete(collection_name=self.collection_name, ids=[memory_id])
        self.client.flush(collection_name=self.collection_name)
