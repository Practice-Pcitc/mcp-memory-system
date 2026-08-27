"""REST API contract tests using dependency overrides."""

from fastapi.testclient import TestClient

from app.dependencies import get_memory_service
from app.main import create_app
from app.services import MemoryService


def test_memory_api_crud_and_search(memory_service: MemoryService) -> None:
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: memory_service

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post(
            "/api/memories",
            json={
                "user_id": "api-user",
                "conversation_id": "api-conversation",
                "content": "API 用户喜欢 MCP",
                "tags": ["mcp"],
            },
        )
        assert created.status_code == 201
        memory_id = created.json()["id"]

        searched = client.post(
            "/api/memories/search",
            json={
                "user_id": "api-user",
                "query": "API 用户喜欢 MCP",
                "top_k": 5,
            },
        )
        assert searched.status_code == 200
        assert searched.json()[0]["id"] == memory_id

        updated = client.put(
            f"/api/memories/{memory_id}?user_id=api-user",
            json={"content": "API 用户喜欢 MCP 和 Milvus"},
        )
        assert updated.status_code == 200
        assert updated.json()["content"].endswith("Milvus")

        listed = client.get("/api/memories?user_id=api-user")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        deleted = client.delete(
            f"/api/memories/{memory_id}?user_id=api-user"
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        missing = client.get(
            f"/api/memories/{memory_id}?user_id=api-user"
        )
        assert missing.status_code == 404

