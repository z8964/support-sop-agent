from fastapi.testclient import TestClient

from app.main import app
from app.services.sop_service import sop_service


client = TestClient(app)


def setup_function() -> None:
    sop_service.reset()


def test_reindex_sops() -> None:
    response = client.post("/api/sops/reindex")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] >= 9
    assert {doc["policy_type"] for doc in body["documents"]} == {
        "refund",
        "logistics",
        "invoice",
    }


def test_list_sops_auto_indexes_documents() -> None:
    response = client.get("/api/sops")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert body[0]["chunk_count"] > 0


def test_search_refund_policy() -> None:
    response = client.post(
        "/api/sops/search",
        json={
            "query": "shipped order direct refund",
            "policy_type": "refund",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["policy_type"] == "refund"
    assert len(body["hits"]) >= 1
    assert body["hits"][0]["chunk"]["section"] == "Shipped Orders"
    assert body["hits"][0]["chunk"]["source"] == "refund_policy.md"


def test_search_invoice_policy() -> None:
    response = client.post(
        "/api/sops/search",
        json={
            "query": "invoice reissue title tax number email",
            "policy_type": "invoice",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["hits"][0]["chunk"]["section"] == "Invoice Reissue"


def test_search_respects_top_k() -> None:
    response = client.post(
        "/api/sops/search",
        json={
            "query": "order customer support",
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["hits"]) == 1

