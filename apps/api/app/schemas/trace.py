from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class TraceStep(BaseModel):
    node: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: str = "success"


class TicketTrace(BaseModel):
    trace_id: str
    ticket_id: str
    steps: list[TraceStep]
    created_at: datetime


class TicketTraceListResponse(BaseModel):
    ticket_id: str
    items: list[TicketTrace]
    total: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

