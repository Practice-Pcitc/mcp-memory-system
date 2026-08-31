"""FastAPI routes used by the Vue3 management interface."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_memory_service
from app.schemas import (
    DeleteMemoryResult,
    MemoryCreate,
    MemoryList,
    MemoryRead,
    MemorySearch,
    MemoryUpdate,
)
from app.services import MemoryService


router = APIRouter()


@router.get("/health")
def health(service: MemoryService = Depends(get_memory_service)) -> dict[str, str]:
    del service
    return {"status": "ok"}


@router.post(
    "/memories",
    response_model=MemoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    payload: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
) -> MemoryRead:
    return service.write_memory(payload)


@router.post("/memories/search", response_model=list[MemoryRead])
def search_memories(
    payload: MemorySearch,
    service: MemoryService = Depends(get_memory_service),
) -> list[MemoryRead]:
    return service.search_memory(payload)


@router.get("/memories", response_model=MemoryList)
def list_memories(
    user_id: str = Query(min_length=1, max_length=128),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    conversation_id: str | None = Query(default=None, max_length=128),
    tags: list[str] | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    project_path: str | None = Query(default=None, max_length=1024),
    include_global: bool = Query(default=True),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryList:
    return service.list_memories(
        user_id=user_id,
        offset=offset,
        limit=limit,
        conversation_id=conversation_id,
        tags=tags,
        start_time=start_time,
        end_time=end_time,
        project_path=project_path,
        include_global=include_global,
    )


@router.get("/memories/{memory_id}", response_model=MemoryRead)
def get_memory(
    memory_id: str,
    user_id: str = Query(min_length=1, max_length=128),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryRead:
    return service.get_memory(memory_id, user_id)


@router.put("/memories/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    user_id: str = Query(min_length=1, max_length=128),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryRead:
    return service.update_memory(memory_id, user_id, payload)


@router.delete("/memories/{memory_id}", response_model=DeleteMemoryResult)
def delete_memory(
    memory_id: str,
    user_id: str = Query(min_length=1, max_length=128),
    service: MemoryService = Depends(get_memory_service),
) -> DeleteMemoryResult:
    return service.delete_memory(memory_id, user_id)
