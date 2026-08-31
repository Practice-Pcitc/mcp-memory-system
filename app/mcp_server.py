"""MCP server exposing long-term memory tools to AI clients."""

from datetime import datetime
import json
import math
import os
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from app.schemas import (
    DeleteMemoryResult,
    MemoryCreate,
    MemoryList,
    MemoryRead,
    MemorySearch,
    MemoryUpdate,
)


mcp = FastMCP(
    "MCP Long-term Memory",
    instructions=(
        "Store and retrieve user-scoped long-term memories. An omitted project_path "
        "means global memory. A project search includes that project and global memory "
        "unless include_global is false. Always pass the authenticated user's user_id."
    ),
)


def _sanitize_url(url: str) -> str:
    """Remove URL credentials before including a backend address in errors."""

    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _http_config() -> tuple[str, float]:
    """Load and validate the trusted MCP-to-REST connection settings."""

    raw_base_url = os.getenv(
        "MCP_API_BASE_URL",
        "http://127.0.0.1:8000/api",
    )
    try:
        parsed = urlsplit(raw_base_url)
        parsed_port = parsed.port
    except ValueError:
        raise RuntimeError(
            "MCP_API_BASE_URL must be a valid absolute HTTP(S) URL"
        ) from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
        or parsed_port is None and parsed.netloc.endswith(":")
    ):
        raise RuntimeError(
            "MCP_API_BASE_URL must be a valid absolute HTTP(S) URL"
        ) from None

    raw_timeout = os.getenv("MCP_API_TIMEOUT_SECONDS", "30")
    try:
        timeout = float(raw_timeout)
    except ValueError:
        raise RuntimeError(
            "MCP_API_TIMEOUT_SECONDS must be a finite positive number"
        ) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError(
            "MCP_API_TIMEOUT_SECONDS must be a finite positive number"
        ) from None
    return raw_base_url.rstrip("/"), timeout


def _memory_response(payload: Any, operation: str) -> dict[str, Any]:
    """Validate one backend memory before exposing it through MCP."""

    try:
        return MemoryRead.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        raise RuntimeError(
            f"Memory backend returned an invalid {operation} response"
        ) from None


def _request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Call the singleton REST backend instead of loading models per MCP process."""

    base_url, timeout = _http_config()
    url = f"{base_url}{path}"
    sanitized_url = _sanitize_url(url)
    body = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        status_code = exc.code
        exc.close()
        raise RuntimeError(
            f"Memory backend returned HTTP {status_code} for "
            f"{method} {sanitized_url}"
        ) from None
    except (URLError, OSError):
        raise RuntimeError(
            f"Cannot reach the memory REST backend at {sanitized_url}. "
            "Start or configure the FastAPI backend and verify MCP_API_BASE_URL. "
            f"Request: {method}."
        ) from None

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Memory backend returned invalid JSON for {method} {path}"
        ) from None


@mcp.tool()
def write_memory(
    content: str,
    user_id: str,
    conversation_id: str | None = None,
    project_path: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one long-term memory and index its semantic embedding."""

    payload = MemoryCreate(
        content=content,
        user_id=user_id,
        conversation_id=conversation_id,
        project_path=project_path,
        tags=tags or [],
        metadata=metadata or {},
    ).model_dump(mode="json", exclude_none=True)
    result = _request_json("POST", "/memories", payload)
    return _memory_response(result, "write")


@mcp.tool()
def search_memory(
    query: str,
    user_id: str,
    top_k: int = 5,
    conversation_id: str | None = None,
    project_path: str | None = None,
    include_global: bool = True,
    tags: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
) -> list[dict[str, Any]]:
    """Search memories using semantic, keyword, or hybrid retrieval."""

    payload = MemorySearch(
        query=query,
        user_id=user_id,
        top_k=top_k,
        conversation_id=conversation_id,
        project_path=project_path,
        include_global=include_global,
        tags=tags or [],
        start_time=start_time,
        end_time=end_time,
        search_mode=search_mode,
    ).model_dump(mode="json", exclude_none=True)
    result = _request_json("POST", "/memories/search", payload)
    if not isinstance(result, list):
        raise RuntimeError("Memory backend returned an invalid search response")
    return [_memory_response(item, "search") for item in result]


@mcp.tool()
def get_memory(memory_id: str, user_id: str) -> dict[str, Any]:
    """Read one user-owned memory by identifier."""

    memory_path = quote(memory_id, safe="")
    query = urlencode({"user_id": user_id})
    result = _request_json("GET", f"/memories/{memory_path}?{query}")
    return _memory_response(result, "get")


@mcp.tool()
def list_memories(
    user_id: str,
    project_path: str | None = None,
    include_global: bool = True,
    conversation_id: str | None = None,
    tags: list[str] | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """List memories with user, project, conversation and tag filters."""

    params: list[tuple[str, str]] = [
        ("user_id", user_id),
        ("offset", str(offset)),
        ("limit", str(limit)),
        ("include_global", str(include_global).lower()),
    ]
    if project_path:
        normalized = MemorySearch(user_id=user_id, query="scope", project_path=project_path)
        params.append(("project_path", normalized.project_path or ""))
    if conversation_id:
        params.append(("conversation_id", conversation_id))
    params.extend(("tags", tag) for tag in tags or [])
    result = _request_json("GET", f"/memories?{urlencode(params)}")
    try:
        return MemoryList.model_validate(result).model_dump(mode="json")
    except ValidationError:
        raise RuntimeError("Memory backend returned an invalid list response") from None


@mcp.tool()
def update_memory(
    memory_id: str,
    user_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    project_path: str | None = None,
    make_global: bool = False,
) -> dict[str, Any]:
    """Edit a memory; set make_global to move it out of a project."""

    raw_payload: dict[str, Any] = {}
    if content is not None:
        raw_payload["content"] = content
    if tags is not None:
        raw_payload["tags"] = tags
    if metadata is not None:
        raw_payload["metadata"] = metadata
    if project_path is not None or make_global:
        raw_payload["project_path"] = None if make_global else project_path
    payload = MemoryUpdate.model_validate(raw_payload).model_dump(
        mode="json", exclude_unset=True
    )
    memory_path = quote(memory_id, safe="")
    query = urlencode({"user_id": user_id})
    result = _request_json("PUT", f"/memories/{memory_path}?{query}", payload)
    return _memory_response(result, "update")


@mcp.tool()
def delete_memory(memory_id: str, user_id: str) -> dict[str, Any]:
    """Delete one user-owned memory and remove its vector from Milvus."""

    memory_path = quote(memory_id, safe="")
    user_query = quote(user_id, safe="")
    result = _request_json(
        "DELETE",
        f"/memories/{memory_path}?user_id={user_query}",
    )
    try:
        return DeleteMemoryResult.model_validate(result).model_dump(mode="json")
    except ValidationError:
        raise RuntimeError(
            "Memory backend returned an invalid delete response"
        ) from None


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
