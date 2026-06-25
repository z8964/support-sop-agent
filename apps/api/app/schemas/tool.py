from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ToolStatus = Literal["success", "failed", "denied", "invalid"]


class UserLookupInput(BaseModel):
    user_id: str = Field(min_length=1)


class OrderLookupInput(BaseModel):
    order_id: str = Field(min_length=1)


class ToolAuditRecord(BaseModel):
    audit_id: str
    tool_name: str
    actor: str
    permission: str
    status: ToolStatus
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    attempts: int = 0
    duration_ms: float = 0.0
    idempotency_key: str | None = None
    idempotent_replay: bool = False
    created_at: datetime


class ToolAuditListResponse(BaseModel):
    items: list[ToolAuditRecord]
    total: int
