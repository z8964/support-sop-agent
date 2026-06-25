from typing import Any

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # Allows the Windows EXE build to use a lighter fallback.
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]

from app.agents.state import TicketWorkflowState
from app.config import get_settings
from app.schemas.ticket import RiskLevel, TicketIntent, TicketStatus, TicketUpdate
from app.services.business_tool_service import (
    ToolExecutionError,
    ToolResult,
    business_tool_service,
)
from app.services.memory_service import memory_service
from app.services.sop_service import sop_service
from app.services.ticket_service import ticket_service
from app.services.trace_service import trace_service


class WorkflowStepLimitError(RuntimeError):
    def __init__(self, state: TicketWorkflowState, max_steps: int) -> None:
        super().__init__(f"Agent workflow exceeded AGENT_MAX_STEPS={max_steps}")
        self.state = state
        self.max_steps = max_steps


def run_ticket_workflow(ticket_id: str) -> TicketWorkflowState:
    ticket = ticket_service.get_ticket(ticket_id)
    initial_state: TicketWorkflowState = {
        "ticket_id": ticket.id,
        "user_id": ticket.user_id,
        "order_id": ticket.order_id,
        "message": ticket.message,
        "trace": [],
        "context": {},
        "memory": {},
        "sop_matches": [],
        "missing_fields": [],
        "workflow_route": "unclassified",
        "tool_errors": [],
        "step_count": 0,
        "need_human_review": False,
        "risk_level": RiskLevel.low.value,
        "ticket_status": TicketStatus.processing.value,
    }

    graph = _build_graph()
    try:
        return graph.invoke(initial_state)
    except WorkflowStepLimitError as exc:
        return _finalize_workflow_failure(
            exc.state,
            reason=str(exc),
            failure_type="step_limit_exceeded",
        )
    except Exception as exc:
        return _finalize_workflow_failure(
            initial_state,
            reason=str(exc),
            failure_type="unexpected_workflow_error",
        )


def _build_graph():
    if StateGraph is None:
        return _SequentialTicketWorkflow()

    workflow = StateGraph(TicketWorkflowState)
    workflow.add_node("intent", _intent_node)
    workflow.add_node("context", _context_node)
    workflow.add_node("memory", _memory_retriever_node)
    workflow.add_node("sop", _sop_node)
    workflow.add_node("decision", _decision_node)
    workflow.add_node("reply", _reply_node)
    workflow.add_node("persist", _persist_node)

    workflow.set_entry_point("intent")
    workflow.add_conditional_edges(
        "intent",
        _route_after_intent,
        {
            "needs_information": "decision",
            "business_flow": "context",
        },
    )
    workflow.add_edge("context", "memory")
    workflow.add_conditional_edges(
        "memory",
        _route_after_memory,
        {
            "knowledge_flow": "sop",
            "direct_decision": "decision",
        },
    )
    workflow.add_edge("sop", "decision")
    workflow.add_edge("decision", "reply")
    workflow.add_edge("reply", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile()


class _SequentialTicketWorkflow:
    def invoke(self, state: TicketWorkflowState) -> TicketWorkflowState:
        state = _intent_node(state)
        if _route_after_intent(state) == "business_flow":
            state = _context_node(state)
            state = _memory_retriever_node(state)
            if _route_after_memory(state) == "knowledge_flow":
                state = _sop_node(state)
        state = _decision_node(state)
        state = _reply_node(state)
        state = _persist_node(state)
        return state


def _intent_node(state: TicketWorkflowState) -> TicketWorkflowState:
    message = state["message"].lower()
    missing_fields: list[str] = []

    if _contains_any(message, ["refund", "退款", "cancel", "取消"]):
        intent = TicketIntent.refund_request.value
        confidence = 0.92
    elif _contains_any(message, ["logistics", "tracking", "package", "快递", "物流"]):
        intent = TicketIntent.logistics_issue.value
        confidence = 0.9
    elif _contains_any(message, ["invoice", "发票", "tax"]):
        intent = TicketIntent.invoice_request.value
        confidence = 0.9
    elif _contains_any(message, ["complaint", "投诉", "angry"]):
        intent = TicketIntent.complaint_escalation.value
        confidence = 0.86
    else:
        intent = TicketIntent.unknown.value
        confidence = 0.45

    if intent in {
        TicketIntent.refund_request.value,
        TicketIntent.logistics_issue.value,
        TicketIntent.invoice_request.value,
    } and not state.get("order_id"):
        missing_fields.append("order_id")

    output = {
        "intent": {
            "intent": intent,
            "confidence": confidence,
            "entities": {"order_id": state.get("order_id")},
            "missing_fields": missing_fields,
        },
        "missing_fields": missing_fields,
        "workflow_route": _workflow_route(intent, missing_fields),
    }
    return _merge(state, output, "intent_agent", {"message": state["message"]}, output)


def _context_node(state: TicketWorkflowState) -> TicketWorkflowState:
    context: dict[str, Any] = {
        "order": None,
        "logistics": None,
        "user": None,
        "ticket_history": [],
    }
    tool_calls: list[dict[str, Any]] = []
    tool_errors = list(state.get("tool_errors", []))
    intent = state["intent"]["intent"]

    def run_tool(call: Any) -> Any:
        try:
            result: ToolResult = call()
            tool_calls.append(
                {
                    "tool": result.tool_name,
                    "attempts": result.attempts,
                    "status": "success",
                }
            )
            return result.value
        except ToolExecutionError as exc:
            error = {
                "tool": exc.tool_name,
                "attempts": exc.attempts,
                "error": str(exc.cause),
            }
            tool_calls.append({**error, "status": "failed"})
            tool_errors.append(error)
            return None

    context["user"] = run_tool(
        lambda: business_tool_service.get_user(state["user_id"])
    )
    context["ticket_history"] = run_tool(
        lambda: business_tool_service.get_ticket_history(state["user_id"])
    )

    order_id = state.get("order_id")
    if order_id and intent in {
        TicketIntent.refund_request.value,
        TicketIntent.logistics_issue.value,
        TicketIntent.invoice_request.value,
    }:
        context["order"] = run_tool(
            lambda: business_tool_service.get_order(order_id)
        )
    if order_id and intent == TicketIntent.logistics_issue.value:
        context["logistics"] = run_tool(
            lambda: business_tool_service.get_logistics(order_id)
        )

    output = {
        "context": context,
        "tool_errors": tool_errors,
        "tool_calls": tool_calls,
    }
    return _merge(
        state,
        output,
        "context_builder",
        {"user_id": state["user_id"], "order_id": order_id},
        output,
        status="degraded" if tool_errors else "success",
    )


def _memory_retriever_node(state: TicketWorkflowState) -> TicketWorkflowState:
    intent = state["intent"]["intent"]
    memory = memory_service.build_user_context(
        user_id=state["user_id"],
        query=state["message"],
        intent=intent,
    )
    output = {"memory": memory}
    return _merge(
        state,
        output,
        "memory_retriever",
        {
            "user_id": state["user_id"],
            "query": state["message"],
            "intent": intent,
        },
        output,
    )


def _sop_node(state: TicketWorkflowState) -> TicketWorkflowState:
    intent = state["intent"]["intent"]
    policy_type = _policy_type_for_intent(intent)
    query_parts = [state["message"], intent]
    order = state.get("context", {}).get("order")
    if order:
        query_parts.append(str(order.get("status")))

    try:
        search = sop_service.search(
            query=" ".join(query_parts),
            policy_type=policy_type,
            top_k=3,
        )
    except Exception as exc:
        tool_errors = [
            *state.get("tool_errors", []),
            {
                "tool": "search_sop",
                "attempts": 1,
                "error": str(exc),
            },
        ]
        output = {"sop_matches": [], "tool_errors": tool_errors}
        return _merge(
            state,
            output,
            "sop_retriever",
            {"query": " ".join(query_parts), "policy_type": policy_type},
            output,
            status="degraded",
        )
    matches = [
        {
            "source": hit.chunk.source,
            "section": hit.chunk.section,
            "policy_type": hit.chunk.policy_type,
            "content": hit.chunk.content,
            "score": hit.score,
        }
        for hit in search.hits
    ]

    output = {"sop_matches": matches}
    return _merge(
        state,
        output,
        "sop_retriever",
        {"query": " ".join(query_parts), "policy_type": policy_type},
        output,
    )


def _decision_node(state: TicketWorkflowState) -> TicketWorkflowState:
    settings = get_settings()
    intent = state["intent"]["intent"]
    context = state.get("context", {})
    order = context.get("order")
    user = context.get("user")
    memory_context = state.get("memory", {})
    missing_fields = state.get("missing_fields", [])
    tool_errors = state.get("tool_errors", [])

    decision = {
        "decision": "needs_manual_review",
        "reason": "The workflow could not confidently resolve the ticket.",
        "next_actions": ["Send the ticket to human review."],
        "policy_refs": _policy_refs(state),
    }
    ticket_status = TicketStatus.pending_human_review.value
    risk_level = RiskLevel.medium.value
    need_human_review = True

    if missing_fields:
        decision = {
            "decision": "request_missing_information",
            "reason": "Required fields are missing.",
            "next_actions": [f"Ask customer to provide {field}." for field in missing_fields],
            "policy_refs": _policy_refs(state),
        }
        ticket_status = TicketStatus.waiting_customer_info.value
        risk_level = RiskLevel.low.value
        need_human_review = False
    elif tool_errors:
        failed_tools = ", ".join(
            sorted({str(error["tool"]) for error in tool_errors})
        )
        decision = {
            "decision": "defer_due_to_tool_failure",
            "reason": f"Required business tools failed: {failed_tools}.",
            "next_actions": [
                "Send the ticket to human review.",
                "Retry the failed tools before taking business action.",
            ],
            "policy_refs": _policy_refs(state),
        }
        ticket_status = TicketStatus.pending_human_review.value
        risk_level = RiskLevel.medium.value
        need_human_review = True
    elif intent == TicketIntent.refund_request.value and order:
        amount = float(order.get("amount", 0))
        order_status = order.get("status")
        high_risk = amount > settings.high_amount_threshold or bool(
            user and user.get("is_vip")
        ) or _memory_requires_human_review(memory_context)
        if order_status == "shipped":
            decision = {
                "decision": "suggest_reject_delivery_or_return_after_receipt",
                "reason": "The order has shipped, so support must not promise a direct refund.",
                "next_actions": [
                    "Tell the customer the order has shipped.",
                    "Suggest rejecting delivery or applying for return refund after receipt.",
                ],
                "policy_refs": _policy_refs(state),
            }
            ticket_status = (
                TicketStatus.pending_human_review.value
                if high_risk
                else TicketStatus.resolved.value
            )
            risk_level = RiskLevel.high.value if high_risk else RiskLevel.medium.value
            need_human_review = high_risk
        elif order_status == "paid":
            decision = {
                "decision": "cancel_unshipped_order",
                "reason": "The order has not shipped and can be cancelled before shipment.",
                "next_actions": [
                    "Confirm the order is not shipped.",
                    "Help the customer cancel the order and request refund.",
                ],
                "policy_refs": _policy_refs(state),
            }
            ticket_status = (
                TicketStatus.pending_human_review.value
                if high_risk
                else TicketStatus.resolved.value
            )
            risk_level = RiskLevel.high.value if high_risk else RiskLevel.low.value
            need_human_review = high_risk
    elif intent == TicketIntent.logistics_issue.value:
        logistics = context.get("logistics")
        stale_days = int(logistics.get("stale_days", 0)) if logistics else 0
        decision = {
            "decision": "create_logistics_follow_up"
            if stale_days > 2
            else "explain_logistics_status",
            "reason": "The logistics status was checked against the support policy.",
            "next_actions": [
                "Explain the latest logistics status.",
                "Create a carrier follow-up if tracking is stale.",
            ],
            "policy_refs": _policy_refs(state),
        }
        ticket_status = TicketStatus.resolved.value
        risk_level = RiskLevel.medium.value if stale_days > 2 else RiskLevel.low.value
        need_human_review = False
    elif intent == TicketIntent.invoice_request.value:
        decision = {
            "decision": "request_invoice_reissue_information",
            "reason": "Invoice reissue requires updated title, tax number, and receiving email.",
            "next_actions": [
                "Ask customer for invoice title.",
                "Ask customer for tax number.",
                "Ask customer for receiving email.",
            ],
            "policy_refs": _policy_refs(state),
        }
        ticket_status = TicketStatus.waiting_customer_info.value
        risk_level = RiskLevel.low.value
        need_human_review = False

    output = {
        "decision": decision,
        "ticket_status": ticket_status,
        "risk_level": risk_level,
        "need_human_review": need_human_review,
    }
    return _merge(state, output, "decision_agent", {"state": _compact_state(state)}, output)


def _reply_node(state: TicketWorkflowState) -> TicketWorkflowState:
    decision = state["decision"]["decision"]
    order = state.get("context", {}).get("order")
    order_status = order.get("status") if order else None

    if decision == "request_missing_information":
        fields = "、".join(state.get("missing_fields", []))
        reply = f"您好，为了继续处理您的问题，请您补充以下信息：{fields}。"
    elif decision == "suggest_reject_delivery_or_return_after_receipt":
        reply = (
            "您好，您的订单目前已经发货，暂时无法直接取消并退款。"
            "您可以在派送时选择拒收，包裹退回后系统会继续处理退款；"
            "如果已经签收，也可以发起退货退款申请，我们会继续协助您处理。"
        )
    elif decision == "cancel_unshipped_order":
        reply = (
            "您好，您的订单目前还未发货，可以为您继续处理取消和退款申请。"
            "我们会根据订单状态推进处理，请您留意后续通知。"
        )
    elif decision == "create_logistics_follow_up":
        reply = (
            "您好，我们查询到您的物流已经较长时间没有更新。"
            "我们会为您创建物流跟进，请您稍后留意新的物流状态。"
        )
    elif decision == "explain_logistics_status":
        reply = (
            f"您好，我们查询到您的订单物流状态为 {order_status or '运输中'}。"
            "目前会继续等待承运商更新，我们也会协助您关注后续进展。"
        )
    elif decision == "request_invoice_reissue_information":
        reply = (
            "您好，可以协助您处理发票重开。请您补充新的发票抬头、税号和接收邮箱，"
            "我们收到后会继续为您处理。"
        )
    else:
        reply = "您好，您的问题需要进一步核实，我们会转人工继续处理。"

    output = {"draft_reply": reply, "final_reply": reply}
    return _merge(state, output, "reply_writer", {"decision": state["decision"]}, output)


def _persist_node(state: TicketWorkflowState) -> TicketWorkflowState:
    intent = TicketIntent(state["intent"]["intent"])
    ticket_update = TicketUpdate(
        status=TicketStatus(state["ticket_status"]),
        intent=intent,
        risk_level=RiskLevel(state["risk_level"]),
        need_human_review=state["need_human_review"],
        final_reply=state.get("final_reply"),
    )
    ticket = ticket_service.update_ticket(state["ticket_id"], ticket_update)
    memory_record = memory_service.write_workflow_outcome(
        user_id=state["user_id"],
        ticket_id=state["ticket_id"],
        intent=state["intent"]["intent"],
        status=state["ticket_status"],
        decision=state["decision"]["decision"],
    )
    output = {
        "ticket": ticket.model_dump(mode="json"),
        "memory": memory_record.model_dump(mode="json"),
    }
    final_state = _merge(
        state,
        {},
        "ticket_update",
        {"ticket_id": state["ticket_id"]},
        output,
    )
    trace_service.save_trace(state["ticket_id"], final_state.get("trace", []))
    return final_state


def _finalize_workflow_failure(
    state: TicketWorkflowState,
    reason: str,
    failure_type: str,
) -> TicketWorkflowState:
    decision = {
        "decision": "defer_due_to_workflow_failure",
        "reason": reason,
        "next_actions": ["Send the ticket to human review."],
        "policy_refs": _policy_refs(state),
    }
    reply = (
        "We could not complete the automated workflow safely. "
        "A human agent will continue processing this ticket."
    )
    trace = [
        *state.get("trace", []),
        {
            "node": "workflow_guard",
            "input": {
                "step_count": state.get("step_count", 0),
                "failure_type": failure_type,
            },
            "output": {"reason": reason, "fallback": "human_review"},
            "status": "failed",
        },
    ]
    ticket = ticket_service.update_ticket(
        state["ticket_id"],
        TicketUpdate(
            status=TicketStatus.pending_human_review,
            intent=TicketIntent(
                state.get("intent", {}).get(
                    "intent", TicketIntent.unknown.value
                )
            ),
            risk_level=RiskLevel.medium,
            need_human_review=True,
            final_reply=reply,
        ),
    )
    final_state: TicketWorkflowState = {
        **state,
        "intent": state.get(
            "intent",
            {
                "intent": TicketIntent.unknown.value,
                "confidence": 0.0,
                "entities": {"order_id": state.get("order_id")},
                "missing_fields": [],
            },
        ),
        "decision": decision,
        "ticket_status": TicketStatus.pending_human_review.value,
        "risk_level": RiskLevel.medium.value,
        "need_human_review": True,
        "draft_reply": reply,
        "final_reply": reply,
        "ticket": ticket.model_dump(mode="json"),
        "trace": trace,
    }
    trace_service.save_trace(state["ticket_id"], trace)
    return final_state


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _policy_type_for_intent(intent: str) -> str | None:
    return {
        TicketIntent.refund_request.value: "refund",
        TicketIntent.logistics_issue.value: "logistics",
        TicketIntent.invoice_request.value: "invoice",
    }.get(intent)


def _workflow_route(intent: str, missing_fields: list[str]) -> str:
    if missing_fields:
        return "needs_information"
    if intent in {
        TicketIntent.refund_request.value,
        TicketIntent.logistics_issue.value,
        TicketIntent.invoice_request.value,
    }:
        return "knowledge_flow"
    return "direct_decision"


def _route_after_intent(state: TicketWorkflowState) -> str:
    if state.get("workflow_route") == "needs_information":
        return "needs_information"
    return "business_flow"


def _route_after_memory(state: TicketWorkflowState) -> str:
    if state.get("workflow_route") == "knowledge_flow":
        return "knowledge_flow"
    return "direct_decision"


def _policy_refs(state: TicketWorkflowState) -> list[dict[str, str]]:
    return [
        {
            "source": match["source"],
            "section": match["section"],
        }
        for match in state.get("sop_matches", [])
    ]


def _memory_requires_human_review(memory_context: dict[str, Any]) -> bool:
    for memory in memory_context.get("memories", []):
        metadata = memory.get("metadata", {})
        if metadata.get("requires_human_review") is True:
            return True
        if memory.get("type") == "risk_signal":
            return True
        if (
            memory.get("type") == "user_preference"
            and "manual confirmation" in memory.get("content", "").lower()
        ):
            return True
    return False


def _compact_state(state: TicketWorkflowState) -> dict[str, Any]:
    return {
        "intent": state.get("intent"),
        "context": state.get("context"),
        "memory": state.get("memory"),
        "sop_matches": state.get("sop_matches"),
        "missing_fields": state.get("missing_fields"),
    }


def _merge(
    state: TicketWorkflowState,
    updates: dict[str, Any],
    node: str,
    step_input: dict[str, Any],
    step_output: dict[str, Any],
    status: str = "success",
) -> TicketWorkflowState:
    step_count = state.get("step_count", 0) + 1
    max_steps = get_settings().agent_max_steps
    if step_count > max_steps:
        raise WorkflowStepLimitError(state, max_steps)
    trace = [
        *state.get("trace", []),
        {
            "node": node,
            "input": step_input,
            "output": step_output,
            "status": status,
        },
    ]
    return {
        **state,
        **updates,
        "step_count": step_count,
        "trace": trace,
    }
