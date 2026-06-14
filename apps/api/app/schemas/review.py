from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.ticket import RiskLevel, Ticket


class ReviewAction(StrEnum):
    approve = "approve"
    edit = "edit"
    reject = "reject"
    escalate = "escalate"


class ReviewStatus(StrEnum):
    approved = "approved"
    edited = "edited"
    rejected = "rejected"
    escalated = "escalated"


class ReviewSubmit(BaseModel):
    action: ReviewAction
    final_reply: str | None = None
    comment: str | None = None
    reviewer_id: str = "demo_reviewer"


class ReviewRecord(BaseModel):
    id: str
    ticket_id: str
    action: ReviewAction
    status: ReviewStatus
    agent_reply: str | None = None
    final_reply: str | None = None
    reviewer_id: str
    comment: str | None = None
    created_at: datetime


class PendingReviewItem(BaseModel):
    ticket_id: str
    message: str
    intent: str
    risk_level: RiskLevel
    agent_reply: str | None
    reason: str | None = None


class PendingReviewListResponse(BaseModel):
    items: list[PendingReviewItem]
    total: int


class ReviewResult(BaseModel):
    review: ReviewRecord
    ticket: Ticket


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

