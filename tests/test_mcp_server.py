"""MCP adapter tests: tools must reuse the running REST backend."""

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError

import app.mcp_server as mcp_server
import pytest


def _memory_payload(content: str = "用户喜欢简洁说明") -> dict[str, Any]:
    return {
        "id": "memory-1",
        "user_id": "demo-user",
        "conversation_id": None,
        "project_path": None,
        "content": content,
        "tags": ["偏好"],
        "metadata": {},
        "status": "active",
        "vector_status": "ready",
        "created_at": "2026-08-27T08:00:00",
        "updated_at": "2026-08-27T08:00:00",
        "score": None,
    }


def test_mcp_tools_bridge_to_rest_backend(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        calls.append((method, path, payload))
        if path == "/memories/search":
            return [_memory_payload()]
        if method == "DELETE":
            return {"memory_id": "memory/1", "deleted": True}
        return _memory_payload(payload["content"] if payload else "")

    monkeypatch.setattr(mcp_server, "_request_json", fake_request, raising=False)
    monkeypatch.setattr(
        mcp_server,
        "get_memory_service",
        lambda: (_ for _ in ()).throw(AssertionError("MCP must not create MemoryService")),
        raising=False,
    )

    created = mcp_server.write_memory(
        content="用户喜欢简洁说明",
        user_id="demo-user",
        tags=["偏好"],
        project_path=r"D:\Work\Memory-System",
    )
    searched = mcp_server.search_memory(
        query="用户喜欢什么？",
        user_id="demo-user",
        top_k=3,
        start_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
        project_path=r"D:\Work\Memory-System",
        include_global=False,
    )
    deleted = mcp_server.delete_memory("memory/1", "demo user")

    assert created["id"] == "memory-1"
    assert searched[0]["content"] == "用户喜欢简洁说明"
    assert deleted["deleted"] is True
    assert calls == [
        (
            "POST",
            "/memories",
            {
                "user_id": "demo-user",
                "content": "用户喜欢简洁说明",
                "tags": ["偏好"],
                "metadata": {},
                "project_path": "d:/work/memory-system",
            },
        ),
        (
            "POST",
            "/memories/search",
            {
                "user_id": "demo-user",
                "query": "用户喜欢什么？",
                "top_k": 3,
                "tags": [],
                "start_time": "2026-08-01T00:00:00Z",
                "project_path": "d:/work/memory-system",
                    "include_global": False,
                    "search_mode": "semantic",
            },
        ),
        ("DELETE", "/memories/memory%2F1?user_id=demo%20user", None),
    ]


def test_network_error_reports_sanitized_backend_url(monkeypatch: Any) -> None:
    monkeypatch.setenv(
        "MCP_API_BASE_URL",
        "http://api-user:secret@127.0.0.1:9/custom-api",
    )
    monkeypatch.setattr(
        mcp_server,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            URLError("offline at http://api-user:secret@127.0.0.1:9/custom-api")
        ),
    )

    with pytest.raises(RuntimeError) as error:
        mcp_server._request_json("POST", "/memories/search", {"query": "hello"})

    message = str(error.value)
    assert "http://127.0.0.1:9/custom-api/memories/search" in message
    assert "api-user" not in message
    assert "secret" not in message
    assert error.value.__cause__ is None


def test_http_error_reports_status_and_sanitized_backend_url(monkeypatch: Any) -> None:
    monkeypatch.setenv(
        "MCP_API_BASE_URL",
        "http://api-user:secret@memory.test/custom-api",
    )

    def raise_http_error(request: Any, timeout: float) -> Any:
        del timeout
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=BytesIO(b'{"detail":"backend warming up"}'),
        )

    monkeypatch.setattr(mcp_server, "urlopen", raise_http_error)

    with pytest.raises(RuntimeError) as error:
        mcp_server._request_json("POST", "/memories/search", {"query": "hello"})

    message = str(error.value)
    assert "HTTP 503" in message
    assert "http://memory.test/custom-api/memories/search" in message
    assert "backend warming up" not in message
    assert "api-user" not in message
    assert "secret" not in message
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    ("tool", "invalid_response"),
    [
        (lambda: mcp_server.write_memory("content", "demo-user"), {}),
        (
            lambda: mcp_server.search_memory("query", "demo-user"),
            [{"unexpected": True}],
        ),
        (lambda: mcp_server.delete_memory("memory-1", "demo-user"), {}),
    ],
)
def test_tools_reject_invalid_backend_response(
    monkeypatch: Any,
    tool: Any,
    invalid_response: Any,
) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_request_json",
        lambda method, path, payload=None: invalid_response,
    )

    with pytest.raises(RuntimeError, match="invalid .* response"):
        tool()


@pytest.mark.parametrize("timeout", ["not-a-number", "nan", "0", "-1"])
def test_invalid_timeout_config_is_diagnostic(
    monkeypatch: Any,
    timeout: str,
) -> None:
    monkeypatch.setenv("MCP_API_TIMEOUT_SECONDS", timeout)

    with pytest.raises(RuntimeError, match="MCP_API_TIMEOUT_SECONDS") as error:
        mcp_server._request_json("POST", "/memories/search", {})

    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "base_url",
    ["memory.test/api", "file:///tmp/memory", "http://"],
)
def test_invalid_base_url_config_is_diagnostic(
    monkeypatch: Any,
    base_url: str,
) -> None:
    monkeypatch.setenv("MCP_API_BASE_URL", base_url)

    with pytest.raises(RuntimeError, match="MCP_API_BASE_URL") as error:
        mcp_server._request_json("POST", "/memories/search", {})

    assert error.value.__cause__ is None


def test_fastmcp_tool_error_does_not_leak_credentials(monkeypatch: Any) -> None:
    monkeypatch.setenv(
        "MCP_API_BASE_URL",
        "http://api-user:secret@memory.test/api",
    )
    monkeypatch.setattr(
        mcp_server,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            URLError("connect http://api-user:secret@memory.test/api failed")
        ),
    )

    with pytest.raises(Exception) as error:
        asyncio.run(
            mcp_server.mcp.call_tool(
                "search_memory",
                {"query": "hello", "user_id": "demo-user"},
            )
        )

    message = str(error.value)
    assert "api-user" not in message
    assert "secret" not in message
