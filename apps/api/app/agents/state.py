from typing import Any, TypedDict


class TicketWorkflowState(TypedDict, total=False):
    ticket_id: str
    user_id: str
    order_id: str | None
    message: str
    intent: dict[str, Any]
    context: dict[str, Any]
    memory: dict[str, Any]
    sop_matches: list[dict[str, Any]]
    decision: dict[str, Any]
    draft_reply: str | None
    final_reply: str | None
    ticket_status: str
    risk_level: str
    need_human_review: bool
    missing_fields: list[str]
    workflow_route: str
    tool_errors: list[dict[str, Any]]
    step_count: int
    trace: list[dict[str, Any]]
