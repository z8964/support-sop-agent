from fastapi.testclient import TestClient

from app.main import app
from app.services.memory_service import memory_service
from app.services.ticket_service import ticket_service
from app.services.trace_service import trace_service


client = TestClient(app)


def setup_function() -> None:
    ticket_service.reset()
    trace_service.reset()
    memory_service.reset()


def test_list_seed_user_memories() -> None:
    response = client.get("/api/memory/users/U1003")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "U1003"
    assert body["total"] == 1
    assert body["items"][0]["type"] == "user_preference"


def test_create_memory() -> None:
    response = client.post(
        "/api/memory",
        json={
            "user_id": "U2001",
            "type": "user_preference",
            "content": "Customer prefers concise replies.",
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "M00000003"
    assert body["content"] == "Customer prefers concise replies."
    assert body["scope"] == "semantic"
    assert body["confidence"] == 1.0
    assert body["status"] == "active"


def test_workflow_reads_and_writes_memory() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "order_id": "OD2026001",
            "message": "我买的耳机已经发货了，但是我现在不想要了，帮我退款。",
        },
    ).json()

    run_response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert run_response.status_code == 200
    body = run_response.json()
    assert "memory_retriever" in [step["node"] for step in body["trace"]]

    memory_response = client.get("/api/memory/users/U1001?type=workflow_outcome")
    assert memory_response.status_code == 200
    memory = memory_response.json()
    assert memory["total"] == 1
    assert memory["items"][0]["metadata"]["ticket_id"] == ticket["id"]
    assert memory["items"][0]["metadata"]["intent"] == "refund_request"
    assert memory["items"][0]["scope"] == "episodic"
    assert memory["items"][0]["source"] == "agent_workflow"


def test_retrieve_only_returns_relevant_memory() -> None:
    client.post(
        "/api/memory",
        json={
            "user_id": "U2001",
            "type": "user_preference",
            "content": "Customer prefers manual confirmation for refunds.",
            "metadata": {"intent": "refund_request"},
            "memory_key": "refund_preference",
            "importance": 0.9,
        },
    )
    client.post(
        "/api/memory",
        json={
            "user_id": "U2001",
            "type": "user_preference",
            "content": "Customer prefers electronic invoices.",
            "metadata": {"intent": "invoice_request"},
            "memory_key": "invoice_preference",
        },
    )

    response = client.post(
        "/api/memory/retrieve",
        json={
            "user_id": "U2001",
            "query": "Please refund my order.",
            "intent": "refund_request",
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["hits"]) == 1
    assert body["hits"][0]["memory"]["memory_key"] == "refund_preference"
    assert "Stable user context" in body["summary"]


def test_forget_memory_hides_it_from_default_list() -> None:
    memory = client.post(
        "/api/memory",
        json={
            "user_id": "U2001",
            "type": "business_fact",
            "content": "The user account is verified.",
            "memory_key": "account_verification",
        },
    ).json()

    delete_response = client.delete(f"/api/memory/{memory['id']}")
    active_response = client.get("/api/memory/users/U2001")
    all_response = client.get(
        "/api/memory/users/U2001?include_inactive=true"
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    assert active_response.json()["total"] == 0
    assert all_response.json()["items"][0]["status"] == "deleted"


def test_structured_risk_memory_changes_workflow_decision() -> None:
    client.post(
        "/api/memory",
        json={
            "user_id": "U1002",
            "type": "risk_signal",
            "scope": "semantic",
            "content": "Recent refund activity requires manual review.",
            "metadata": {
                "intent": "refund_request",
                "requires_human_review": True,
            },
            "source": "risk_engine",
            "confidence": 0.95,
            "importance": 1.0,
            "memory_key": "refund_risk",
        },
    )
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1002",
            "order_id": "OD2026002",
            "message": "Please cancel and refund this order.",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "cancel_unshipped_order"
    assert body["status"] == "pending_human_review"
    assert body["risk_level"] == "high"
