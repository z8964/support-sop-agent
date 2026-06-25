import httpx
import pytest

from app.services.embedding_service import OpenAIEmbeddingProvider


def test_openai_embedding_provider_batches_and_orders_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        captured_request.update(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        base_url="https://embedding.example/v1",
        model_name="bge-m3",
        dimensions=2,
    )

    embeddings = provider.embed_many(["refund policy", "invoice policy"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert captured_request["url"] == "https://embedding.example/v1/embeddings"
    assert captured_request["json"] == {
        "model": "bge-m3",
        "input": ["refund policy", "invoice policy"],
        "dimensions": 2,
    }


def test_openai_embedding_provider_requires_api_key() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key=None,
        base_url=None,
        model_name="text-embedding-3-small",
        dimensions=1536,
    )

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.embed_many(["refund policy"])
