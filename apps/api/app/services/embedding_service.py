import hashlib
import math
import re
from typing import Protocol

import httpx

from app.config import get_settings


class EmbeddingProvider(Protocol):
    name: str
    model_name: str
    dimensions: int

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    name = "hash"
    model_name = "deterministic-hash-v1"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._features(text):
            index = self._hash(token) % self.dimensions
            sign = 1.0 if self._hash(f"sign:{token}") % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def _features(self, text: str) -> list[str]:
        normalized = text.lower()
        latin_tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        cjk_bigrams = [
            "".join(cjk_chars[index : index + 2])
            for index in range(max(len(cjk_chars) - 1, 0))
        ]
        cjk_trigrams = [
            "".join(cjk_chars[index : index + 3])
            for index in range(max(len(cjk_chars) - 2, 0))
        ]

        features: list[str] = []
        features.extend(token for token in latin_tokens if len(token) > 1)
        features.extend(cjk_chars)
        features.extend(cjk_bigrams)
        features.extend(cjk_trigrams)
        return features

    def _hash(self, value: str) -> int:
        digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big", signed=False)


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str | None,
        base_url: str | None,
        model_name: str,
        dimensions: int,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model_name = model_name
        self.dimensions = dimensions

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when RAG_EMBEDDING_PROVIDER=openai"
            )

        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "input": texts,
                "dimensions": self.dimensions,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        embeddings = [item["embedding"] for item in data]
        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding provider returned an unexpected result count")
        return embeddings


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    @property
    def dimensions(self) -> int:
        return self.provider.dimensions

    @property
    def index_signature(self) -> str:
        return f"{self.provider_name}:{self.model_name}:{self.dimensions}"

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed_many(texts)


def build_embedding_service() -> EmbeddingService:
    settings = get_settings()
    provider_name = settings.rag_embedding_provider.strip().lower()
    if provider_name == "hash":
        return EmbeddingService(HashEmbeddingProvider())
    if provider_name in {"openai", "openai-compatible"}:
        return EmbeddingService(
            OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model_name=settings.openai_embedding_model,
                dimensions=settings.openai_embedding_dimensions,
            )
        )
    raise ValueError(f"Unsupported RAG embedding provider: {provider_name}")


embedding_service = build_embedding_service()
