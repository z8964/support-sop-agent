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

