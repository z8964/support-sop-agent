from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal[
    "user_preference",
    "business_fact",
    "risk_signal",
    "ticket_summary",
    "workflow_outcome",
    "successful_strategy",
]
MemoryScope = Literal["semantic", "episodic", "procedural"]
MemoryStatus = Literal["active", "superseded", "deleted"]


class MemoryRecord(BaseModel):
    id: str
    user_id: str
    type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    scope: MemoryScope = "semantic"
    source: str = "manual"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_key: str | None = None
    status: MemoryStatus = "active"
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None


class MemoryCreate(BaseModel):
    user_id: str = Field(min_length=1)
    type: MemoryType
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scope: MemoryScope = "semantic"
    source: str = "manual"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_key: str | None = None
    expires_at: datetime | None = None


class MemoryRetrieveRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    intent: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class MemorySearchHit(BaseModel):
    memory: MemoryRecord
    score: float
    matched_terms: list[str]


class MemoryRetrieveResponse(BaseModel):
    user_id: str
    query: str
    hits: list[MemorySearchHit]
    summary: str


class MemoryListResponse(BaseModel):
    user_id: str
    items: list[MemoryRecord]
    total: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
