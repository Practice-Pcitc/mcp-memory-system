"""MCP server exposing long-term memory tools to AI clients."""

from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_memory_service
from app.schemas import MemoryCreate, MemorySearch


mcp = FastMCP(
    "MCP Long-term Memory",
    instructions=(
        "Store and retrieve user-scoped long-term memories. "
        "Always pass the authenticated user's user_id and never search across users."
    ),
)


@mcp.tool()
def write_memory(
    content: str,
    user_id: str,
    conversation_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one long-term memory and index its semantic embedding."""

    memory = get_memory_service().write_memory(
        MemoryCreate(
            content=content,
            user_id=user_id,
            conversation_id=conversation_id,
            tags=tags or [],
            metadata=metadata or {},
        )
    )
    return memory.model_dump(mode="json")


@mcp.tool()
def search_memory(
    query: str,
    user_id: str,
    top_k: int = 5,
    conversation_id: str | None = None,
    tags: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Semantically search active memories belonging to one user."""

    memories = get_memory_service().search_memory(
        MemorySearch(
            query=query,
            user_id=user_id,
            top_k=top_k,
            conversation_id=conversation_id,
            tags=tags or [],
            start_time=start_time,
            end_time=end_time,
        )
    )
    return [memory.model_dump(mode="json") for memory in memories]


@mcp.tool()
def delete_memory(memory_id: str, user_id: str) -> dict[str, Any]:
    """Delete one user-owned memory and remove its vector from Milvus."""

    result = get_memory_service().delete_memory(memory_id, user_id)
    return result.model_dump(mode="json")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

