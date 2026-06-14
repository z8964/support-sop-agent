from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class TicketIntent(StrEnum):
    refund_request = "refund_request"
    logistics_issue = "logistics_issue"
    invoice_request = "invoice_request"
    complaint_escalation = "complaint_escalation"
    unknown = "unknown"


class TicketStatus(StrEnum):
    created = "created"
    processing = "processing"
    waiting_customer_info = "waiting_customer_info"
    pending_human_review = "pending_human_review"
    resolved = "resolved"
    escalated = "escalated"
    failed = "failed"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class TicketCreate(BaseModel):
    user_id: str = Field(min_length=1)
    order_id: str | None = None
    message: str = Field(min_length=1)
    channel: str = "web"


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    intent: TicketIntent | None = None
    risk_level: RiskLevel | None = None
    need_human_review: bool | None = None
    final_reply: str | None = None


class Ticket(BaseModel):
    id: str
    user_id: str
    order_id: str | None = None
    message: str
    channel: str
    intent: TicketIntent = TicketIntent.unknown
    status: TicketStatus = TicketStatus.created
    risk_level: RiskLevel = RiskLevel.low
    need_human_review: bool = False
    final_reply: str | None = None
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    items: list[Ticket]
    total: int
    limit: int
    offset: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

