from typing import Literal

from pydantic import BaseModel, Field


OrderStatus = Literal["paid", "shipped", "delivered", "cancelled", "refunded"]
LogisticsStatus = Literal["pending", "in_transit", "delivered", "no_update", "lost"]
UserLevel = Literal["normal", "vip", "enterprise"]
TicketStatus = Literal["resolved", "pending_human_review", "waiting_customer_info", "escalated"]


class OrderItem(BaseModel):
    sku: str
    name: str
    quantity: int = Field(gt=0)


class MockOrder(BaseModel):
    order_id: str
    user_id: str
    status: OrderStatus
    amount: float = Field(ge=0)
    items: list[OrderItem]
    created_at: str
    shipped_at: str | None = None


class LogisticsEvent(BaseModel):
    time: str
    description: str


class MockLogistics(BaseModel):
    order_id: str
    carrier: str
    tracking_no: str
    status: LogisticsStatus
    last_update_at: str | None = None
    stale_days: int = Field(default=0, ge=0)
    events: list[LogisticsEvent]


class MockUser(BaseModel):
    user_id: str
    name: str
    level: UserLevel
    is_vip: bool
    complaint_count_30d: int = Field(ge=0)
    ticket_count_30d: int = Field(ge=0)


class MockTicketHistoryItem(BaseModel):
    ticket_id: str
    user_id: str
    order_id: str | None = None
    intent: str
    status: TicketStatus
    summary: str
    created_at: str


class EscalationCreate(BaseModel):
    ticket_id: str
    reason: str
    risk_level: Literal["medium", "high"] = "medium"


class MockEscalation(BaseModel):
    escalation_id: str
    ticket_id: str
    reason: str
    risk_level: Literal["medium", "high"]
    status: Literal["created"] = "created"

