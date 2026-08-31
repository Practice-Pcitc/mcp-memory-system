"""Contracts shared by MCP tools, REST endpoints and services."""

from datetime import datetime
import ntpath
import posixpath
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _clean_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_tag in tags:
        tag = raw_tag.strip()
        if tag and tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result


def normalize_project_path(value: str | None) -> str | None:
    """Return one stable absolute path; an empty value denotes global memory."""

    if value is None or not value.strip():
        return None
    raw = value.strip()
    if any(ord(char) < 32 for char in raw):
        raise ValueError("project_path must not contain control characters")

    windows_path = bool(re.match(r"^[A-Za-z]:[\\/]", raw)) or raw.startswith(
        ("\\\\", "//")
    )
    if windows_path:
        normalized = ntpath.normcase(ntpath.normpath(raw)).replace("\\", "/")
        if not (re.match(r"^[a-z]:/", normalized) or normalized.startswith("//")):
            raise ValueError("project_path must be an absolute path")
    else:
        normalized = posixpath.normpath(raw)
        if not normalized.startswith("/"):
            raise ValueError("project_path must be an absolute path")

    if len(normalized) > 1024:
        raise ValueError("project_path must not exceed 1024 characters")
    return normalized


class MemoryCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    project_path: str | None = Field(default=None, max_length=1024)
    content: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id", "conversation_id", "content")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)

    @field_validator("project_path")
    @classmethod
    def normalize_scope(cls, value: str | None) -> str | None:
        return normalize_project_path(value)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=50_000)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    project_path: str | None = Field(default=None, max_length=1024)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def normalize_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value) if value is not None else None

    @field_validator("project_path")
    @classmethod
    def normalize_scope(cls, value: str | None) -> str | None:
        return normalize_project_path(value)


class MemorySearch(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=100)
    conversation_id: str | None = Field(default=None, max_length=128)
    project_path: str | None = Field(default=None, max_length=1024)
    include_global: bool = True
    search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic"
    tags: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("user_id", "query", "conversation_id")
    @classmethod
    def strip_search_strings(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def normalize_search_tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)

    @field_validator("project_path")
    @classmethod
    def normalize_scope(cls, value: str | None) -> str | None:
        return normalize_project_path(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "MemorySearch":
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("start_time must not be later than end_time")
        return self


class MemoryRead(BaseModel):
    id: str
    user_id: str
    conversation_id: str | None
    project_path: str | None = None
    content: str
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    vector_status: str
    created_at: datetime
    updated_at: datetime
    score: float | None = None


class MemoryList(BaseModel):
    items: list[MemoryRead]
    total: int
    offset: int
    limit: int


class DeleteMemoryResult(BaseModel):
    memory_id: str
    deleted: bool
