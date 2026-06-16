import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VectorDocument:
    id: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


@dataclass(frozen=True)
class VectorSearchResult:
    document: VectorDocument
    vector_score: float


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._documents: dict[str, VectorDocument] = {}

    def reset(self) -> None:
        self._documents.clear()

    def upsert(self, documents: list[VectorDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document

    def count(self) -> int:
        return len(self._documents)

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        results: list[VectorSearchResult] = []
        for document in self._documents.values():
            if where and not self._matches(document.metadata, where):
                continue
            vector_score = self._cosine_similarity(query_embedding, document.embedding)
            results.append(
                VectorSearchResult(document=document, vector_score=vector_score)
            )

        results.sort(key=lambda result: result.vector_score, reverse=True)
        return results[:top_k]

    def _matches(self, metadata: dict[str, Any], where: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in where.items())

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)


vector_store = InMemoryVectorStore()

