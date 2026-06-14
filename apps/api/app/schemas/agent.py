from typing import Any

from pydantic import BaseModel

from app.schemas.ticket import RiskLevel, TicketStatus


class AgentTraceStep(BaseModel):
    node: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: str = "success"


class AgentRunResponse(BaseModel):
    ticket_id: str
    status: TicketStatus
    intent: str
    risk_level: RiskLevel
    need_human_review: bool
    decision: dict[str, Any]
    final_reply: str | None
    trace: list[AgentTraceStep]

