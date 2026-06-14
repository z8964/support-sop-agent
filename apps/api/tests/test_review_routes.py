from fastapi.testclient import TestClient

from app.main import app
from app.services.review_service import review_service
from app.services.ticket_service import ticket_service
from app.services.trace_service import trace_service


client = TestClient(app)


def setup_function() -> None:
    ticket_service.reset()
    trace_service.reset()
    review_service.reset()


def _create_high_risk_ticket() -> dict:
    ticket = client.post(
        "/api/tickets",
        json={
            "user_id": "U1003",
            "order_id": "OD2026003",
            "message": "这个订单我要退款",
        },
    ).json()
    client.post(f"/api/tickets/{ticket['id']}/run")
    return client.get(f"/api/tickets/{ticket['id']}").json()


def test_list_pending_reviews() -> None:
    ticket = _create_high_risk_ticket()

    response = client.get("/api/reviews/pending")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["ticket_id"] == ticket["id"]
    assert body["items"][0]["risk_level"] == "high"


def test_approve_review_resolves_ticket() -> None:
    ticket = _create_high_risk_ticket()

    response = client.post(
        f"/api/reviews/{ticket['id']}",
        json={
            "action": "approve",
            "comment": "Looks good.",
            "reviewer_id": "reviewer_1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review"]["status"] == "approved"
    assert body["ticket"]["status"] == "resolved"
    assert body["ticket"]["need_human_review"] is False


def test_edit_review_uses_custom_reply() -> None:
    ticket = _create_high_risk_ticket()
    custom_reply = "您好，该高金额退款申请已通过人工审核，我们会继续为您处理。"

    response = client.post(
        f"/api/reviews/{ticket['id']}",
        json={
            "action": "edit",
            "final_reply": custom_reply,
            "comment": "Adjusted wording.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review"]["status"] == "edited"
    assert body["review"]["final_reply"] == custom_reply
    assert body["ticket"]["final_reply"] == custom_reply
    assert body["ticket"]["status"] == "resolved"


def test_escalate_review_escalates_ticket() -> None:
    ticket = _create_high_risk_ticket()

    response = client.post(
        f"/api/reviews/{ticket['id']}",
        json={
            "action": "escalate",
            "comment": "Needs supervisor approval.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review"]["status"] == "escalated"
    assert body["ticket"]["status"] == "escalated"


def test_review_non_pending_ticket_returns_409() -> None:
    ticket = client.post(
        "/api/tickets",
        json={"user_id": "U1001", "message": "普通问题"},
    ).json()

    response = client.post(
        f"/api/reviews/{ticket['id']}",
        json={"action": "approve"},
    )

    assert response.status_code == 409


def test_list_review_history() -> None:
    ticket = _create_high_risk_ticket()
    client.post(
        f"/api/reviews/{ticket['id']}",
        json={"action": "approve"},
    )

    response = client.get(f"/api/reviews/{ticket['id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "R00000001"

