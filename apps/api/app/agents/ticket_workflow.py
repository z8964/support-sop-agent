from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.state import TicketWorkflowState
from app.config import get_settings
from app.schemas.ticket import RiskLevel, TicketIntent, TicketStatus, TicketUpdate
from app.services.mock_data import LOGISTICS, ORDERS, TICKET_HISTORY, USERS
from app.services.sop_service import sop_service
from app.services.ticket_service import ticket_service
from app.services.trace_service import trace_service


def run_ticket_workflow(ticket_id: str) -> TicketWorkflowState:
    ticket = ticket_service.get_ticket(ticket_id)
    initial_state: TicketWorkflowState = {
        "ticket_id": ticket.id,
        "user_id": ticket.user_id,
        "order_id": ticket.order_id,
        "message": ticket.message,
        "trace": [],
        "context": {},
        "sop_matches": [],
        "missing_fields": [],
        "need_human_review": False,
        "risk_level": RiskLevel.low.value,
        "ticket_status": TicketStatus.processing.value,
    }

    graph = _build_graph()
    return graph.invoke(initial_state)


def _build_graph():
    workflow = StateGraph(TicketWorkflowState)
    workflow.add_node("intent", _intent_node)
    workflow.add_node("context", _context_node)
    workflow.add_node("sop", _sop_node)
    workflow.add_node("decision", _decision_node)
    workflow.add_node("reply", _reply_node)
    workflow.add_node("persist", _persist_node)

    workflow.set_entry_point("intent")
    workflow.add_edge("intent", "context")
    workflow.add_edge("context", "sop")
    workflow.add_edge("sop", "decision")
    workflow.add_edge("decision", "reply")
    workflow.add_edge("reply", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile()


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
    }
    return _merge(state, output, "intent_agent", {"message": state["message"]}, output)


def _context_node(state: TicketWorkflowState) -> TicketWorkflowState:
    context: dict[str, Any] = {
        "order": None,
        "logistics": None,
        "user": USERS.get(state["user_id"]).model_dump()
        if state["user_id"] in USERS
        else None,
        "ticket_history": [
            item.model_dump() for item in TICKET_HISTORY.get(state["user_id"], [])
        ],
    }

    order_id = state.get("order_id")
    if order_id:
        order = ORDERS.get(order_id)
        logistics = LOGISTICS.get(order_id)
        context["order"] = order.model_dump() if order else None
        context["logistics"] = logistics.model_dump() if logistics else None

    output = {"context": context}
    return _merge(
        state,
        output,
        "context_builder",
        {"user_id": state["user_id"], "order_id": order_id},
        output,
    )


def _sop_node(state: TicketWorkflowState) -> TicketWorkflowState:
    intent = state["intent"]["intent"]
    policy_type = _policy_type_for_intent(intent)
    query_parts = [state["message"], intent]
    order = state.get("context", {}).get("order")
    if order:
        query_parts.append(str(order.get("status")))

    search = sop_service.search(
        query=" ".join(query_parts),
        policy_type=policy_type,
        top_k=3,
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
    missing_fields = state.get("missing_fields", [])

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
    elif intent == TicketIntent.refund_request.value and order:
        amount = float(order.get("amount", 0))
        order_status = order.get("status")
        high_risk = amount > settings.high_amount_threshold or bool(
            user and user.get("is_vip")
        )
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
    output = {"ticket": ticket.model_dump(mode="json")}
    final_state = _merge(
        state,
        {},
        "ticket_update",
        {"ticket_id": state["ticket_id"]},
        output,
    )
    trace_service.save_trace(state["ticket_id"], final_state.get("trace", []))
    return final_state


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _policy_type_for_intent(intent: str) -> str | None:
    return {
        TicketIntent.refund_request.value: "refund",
        TicketIntent.logistics_issue.value: "logistics",
        TicketIntent.invoice_request.value: "invoice",
    }.get(intent)


def _policy_refs(state: TicketWorkflowState) -> list[dict[str, str]]:
    return [
        {
            "source": match["source"],
            "section": match["section"],
        }
        for match in state.get("sop_matches", [])
    ]


def _compact_state(state: TicketWorkflowState) -> dict[str, Any]:
    return {
        "intent": state.get("intent"),
        "context": state.get("context"),
        "sop_matches": state.get("sop_matches"),
        "missing_fields": state.get("missing_fields"),
    }


def _merge(
    state: TicketWorkflowState,
    updates: dict[str, Any],
    node: str,
    step_input: dict[str, Any],
    step_output: dict[str, Any],
) -> TicketWorkflowState:
    trace = [
        *state.get("trace", []),
        {
            "node": node,
            "input": step_input,
            "output": step_output,
            "status": "success",
        },
    ]
    return {
        **state,
        **updates,
        "trace": trace,
    }
