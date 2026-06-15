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


def test_run_shipped_refund_workflow() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "order_id": "OD2026001",
            "message": "我买的耳机已经发货了，但是我现在不想要了，帮我退款。",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "refund_request"
    assert body["status"] == "resolved"
    assert body["risk_level"] == "medium"
    assert body["need_human_review"] is False
    assert body["decision"]["decision"] == "suggest_reject_delivery_or_return_after_receipt"
    assert "已经发货" in body["final_reply"]
    assert "直接取消并退款" in body["final_reply"]
    assert [step["node"] for step in body["trace"]] == [
        "intent_agent",
        "context_builder",
        "memory_retriever",
        "sop_retriever",
        "decision_agent",
        "reply_writer",
        "ticket_update",
    ]

    updated = client.get(f"/api/tickets/{ticket['id']}").json()
    assert updated["status"] == "resolved"
    assert updated["intent"] == "refund_request"
    assert updated["final_reply"] == body["final_reply"]

    trace_response = client.get(f"/api/tickets/{ticket['id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["ticket_id"] == ticket["id"]
    assert trace["trace_id"] == "TR00000001"
    assert [step["node"] for step in trace["steps"]] == [
        "intent_agent",
        "context_builder",
        "memory_retriever",
        "sop_retriever",
        "decision_agent",
        "reply_writer",
        "ticket_update",
    ]


def test_run_high_value_refund_requires_human_review() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1003",
            "order_id": "OD2026003",
            "message": "这个订单我要退款",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "refund_request"
    assert body["status"] == "pending_human_review"
    assert body["risk_level"] == "high"
    assert body["need_human_review"] is True


def test_run_missing_order_id_requests_information() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "message": "我不想要了，帮我退款",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting_customer_info"
    assert body["decision"]["decision"] == "request_missing_information"
    assert "order_id" in body["final_reply"]


def test_run_invoice_workflow_requests_invoice_fields() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1005",
            "order_id": "OD2026005",
            "message": "发票抬头写错了，能帮我重开吗？",
        },
    ).json()

    response = client.post(f"/api/tickets/{ticket['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "invoice_request"
    assert body["status"] == "waiting_customer_info"
    assert body["decision"]["decision"] == "request_invoice_reissue_information"
    assert "发票抬头" in body["final_reply"]


def test_run_unknown_ticket_returns_404() -> None:
    response = client.post("/api/tickets/T-NOT-FOUND/run")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_get_trace_before_workflow_returns_404() -> None:
    ticket = client.post(
        "/api/tickets",
        json={"user_id": "U1001", "message": "我不想要了，帮我退款"},
    ).json()

    response = client.get(f"/api/tickets/{ticket['id']}/trace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Trace not found"


def test_list_ticket_traces() -> None:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1002",
            "order_id": "OD2026002",
            "message": "订单还没发货，帮我取消并退款",
        },
    ).json()

    client.post(f"/api/tickets/{ticket['id']}/run")
    client.post(f"/api/tickets/{ticket['id']}/run")
    response = client.get(f"/api/tickets/{ticket['id']}/traces")

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket["id"]
    assert body["total"] == 2
    assert [item["trace_id"] for item in body["items"]] == [
        "TR00000001",
        "TR00000002",
    ]
