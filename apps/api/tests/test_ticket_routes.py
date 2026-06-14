from fastapi.testclient import TestClient

from app.main import app
from app.services.ticket_service import ticket_service


client = TestClient(app)


def setup_function() -> None:
    ticket_service.reset()


def test_create_ticket() -> None:
    response = client.post(
        "/api/tickets",
        json={
            "user_id": "U1001",
            "order_id": "OD2026001",
            "message": "我不想要了，帮我退款",
            "channel": "web",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "T00000001"
    assert body["status"] == "created"
    assert body["intent"] == "unknown"
    assert body["need_human_review"] is False


def test_get_ticket() -> None:
    created = client.post(
        "/api/tickets",
        json={"user_id": "U1001", "message": "Where is my package?"},
    ).json()

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json()["message"] == "Where is my package?"


def test_get_unknown_ticket_returns_404() -> None:
    response = client.get("/api/tickets/T-NOT-FOUND")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_list_tickets_with_filters() -> None:
    first = client.post(
        "/api/tickets",
        json={"user_id": "U1001", "message": "Refund please"},
    ).json()
    client.post(
        "/api/tickets",
        json={"user_id": "U1002", "message": "Need invoice"},
    )
    client.patch(
        f"/api/tickets/{first['id']}",
        json={"intent": "refund_request", "status": "processing"},
    )

    response = client.get("/api/tickets?intent=refund_request&status=processing")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == first["id"]


def test_update_ticket() -> None:
    created = client.post(
        "/api/tickets",
        json={"user_id": "U1003", "message": "This refund is urgent"},
    ).json()

    response = client.patch(
        f"/api/tickets/{created['id']}",
        json={
            "intent": "refund_request",
            "status": "pending_human_review",
            "risk_level": "high",
            "need_human_review": True,
            "final_reply": "We will review this request.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "refund_request"
    assert body["status"] == "pending_human_review"
    assert body["risk_level"] == "high"
    assert body["need_human_review"] is True
    assert body["final_reply"] == "We will review this request."

