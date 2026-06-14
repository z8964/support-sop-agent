from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_mock_order() -> None:
    response = client.get("/mock/orders/OD2026001")

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "OD2026001"
    assert body["status"] == "shipped"
    assert body["amount"] == 399


def test_get_unknown_order_returns_404() -> None:
    response = client.get("/mock/orders/UNKNOWN")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_get_mock_logistics() -> None:
    response = client.get("/mock/logistics/OD2026004")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_update"
    assert body["stale_days"] == 3


def test_get_mock_user() -> None:
    response = client.get("/mock/users/U1003")

    assert response.status_code == 200
    body = response.json()
    assert body["is_vip"] is True
    assert body["level"] == "vip"


def test_get_mock_ticket_history() -> None:
    response = client.get("/mock/users/U1001/tickets")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["intent"] == "logistics_issue"


def test_create_mock_escalation() -> None:
    response = client.post(
        "/mock/escalations",
        json={
            "ticket_id": "T202606140001",
            "reason": "high_value_refund",
            "risk_level": "high",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["escalation_id"].startswith("E")
    assert body["status"] == "created"
    assert body["risk_level"] == "high"

