from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal["user_preference", "ticket_summary", "workflow_outcome"]


class MemoryRecord(BaseModel):
    id: str
    user_id: str
    type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MemoryCreate(BaseModel):
    user_id: str = Field(min_length=1)
    type: MemoryType
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryListResponse(BaseModel):
    user_id: str
    items: list[MemoryRecord]
    total: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

