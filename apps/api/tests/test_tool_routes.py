from fastapi.testclient import TestClient

from app.main import app
from app.services.business_tool_service import business_tool_service


client = TestClient(app)


def setup_function() -> None:
    business_tool_service.reset()


def test_list_tool_audits() -> None:
    business_tool_service.get_order("OD2026001")

    response = client.get("/api/tools/audits?tool_name=get_order")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["tool_name"] == "get_order"
    assert body["items"][0]["permission"] == "order:read"
    assert body["items"][0]["status"] == "success"
