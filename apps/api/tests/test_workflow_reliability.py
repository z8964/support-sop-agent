from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.services.business_tool_service import (
    ToolExecutionError,
    business_tool_service,
)
from app.services.memory_service import memory_service
from app.services.ticket_service import ticket_service
from app.services.trace_service import trace_service


client = TestClient(app)


def setup_function() -> None:
    ticket_service.reset()
    trace_service.reset()
    memory_service.reset()
    business_tool_service.reset()


def test_missing_order_routes_directly_to_information_request() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "message": "Please refund my order.",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "request_missing_information"
    assert [step["node"] for step in body["trace"]] == [
        "intent_agent",
        "decision_agent",
        "action_executor",
        "reply_writer",
        "ticket_update",
    ]


def test_business_tool_failure_degrades_to_human_review(
    monkeypatch,
) -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "order_id": "OD2026001",
            "message": "Refund this shipped order.",
        },
    ).json()

    monkeypatch.setattr(
        business_tool_service,
        "get_order",
        lambda order_id: (_ for _ in ()).throw(
            ToolExecutionError("get_order", 3, RuntimeError("timeout"))
        ),
    )

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_human_review"
    assert body["need_human_review"] is True
    assert body["decision"]["decision"] == "defer_due_to_tool_failure"
    context_step = next(
        step for step in body["trace"] if step["node"] == "context_builder"
    )
    assert context_step["status"] == "degraded"
    assert context_step["output"]["tool_calls"][-1] == {
        "tool": "get_order",
        "attempts": 3,
        "error": "timeout",
        "status": "failed",
    }


def test_unknown_intent_skips_sop_retrieval() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "message": "I need some help with my account.",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    nodes = [step["node"] for step in response.json()["trace"]]
    assert "context_builder" in nodes
    assert "memory_retriever" in nodes
    assert "sop_retriever" not in nodes


def test_step_budget_failure_is_persisted_and_sent_to_human_review(
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "agent_max_steps", 2)
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "order_id": "OD2026001",
            "message": "Refund this shipped order.",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_human_review"
    assert body["decision"]["decision"] == "defer_due_to_workflow_failure"
    assert body["trace"][-1]["node"] == "workflow_guard"
    assert body["trace"][-1]["status"] == "failed"

    saved_ticket = client.get(f"/api/tickets/{ticket['id']}").json()
    assert saved_ticket["status"] == "pending_human_review"


def test_human_review_action_is_idempotent_across_workflow_runs() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1003",
            "order_id": "OD2026003",
            "message": "Please refund this high-value order.",
        },
    ).json()

    first = client.post(f"/api/tickets/{ticket['id']}/run").json()
    second = client.post(f"/api/tickets/{ticket['id']}/run").json()

    first_action = next(
        step for step in first["trace"] if step["node"] == "action_executor"
    )["output"]["executed_actions"][0]
    second_action = next(
        step for step in second["trace"] if step["node"] == "action_executor"
    )["output"]["executed_actions"][0]

    assert first_action["idempotent_replay"] is False
    assert second_action["idempotent_replay"] is True
    assert first_action["result"] == second_action["result"]
