import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.config import get_settings


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


class VectorStore(Protocol):
    backend_name: str

    def reset(self) -> None: ...
    def upsert(self, documents: list[VectorDocument]) -> None: ...
    def count(self) -> int: ...
    def all_documents(self) -> list[VectorDocument]: ...
    def get_index_metadata(self) -> dict[str, str]: ...
    def set_index_metadata(self, metadata: dict[str, str]) -> None: ...
    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]: ...


class InMemoryVectorStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._documents: dict[str, VectorDocument] = {}
        self._index_metadata: dict[str, str] = {}

    def reset(self) -> None:
        self._documents.clear()
        self._index_metadata.clear()

    def upsert(self, documents: list[VectorDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document

    def count(self) -> int:
        return len(self._documents)

    def all_documents(self) -> list[VectorDocument]:
        return list(self._documents.values())

    def get_index_metadata(self) -> dict[str, str]:
        return dict(self._index_metadata)

    def set_index_metadata(self, metadata: dict[str, str]) -> None:
        self._index_metadata = dict(metadata)

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
        return cosine_similarity(left, right)


class SQLiteVectorStore:
    backend_name = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM vector_documents")
            connection.execute("DELETE FROM vector_index_metadata")

    def upsert(self, documents: list[VectorDocument]) -> None:
        rows = [
            (
                document.id,
                document.content,
                json.dumps(document.metadata, ensure_ascii=False, sort_keys=True),
                json.dumps(document.embedding),
            )
            for document in documents
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO vector_documents (
                    id, content, metadata_json, embedding_json
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json
                """,
                rows,
            )

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS document_count FROM vector_documents"
            ).fetchone()
        return int(row["document_count"])

    def all_documents(self) -> list[VectorDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, content, metadata_json, embedding_json
                FROM vector_documents
                ORDER BY id
                """
            ).fetchall()
        return [self._deserialize(row) for row in rows]

    def get_index_metadata(self) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM vector_index_metadata"
            ).fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def set_index_metadata(self, metadata: dict[str, str]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO vector_index_metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                list(metadata.items()),
            )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        results: list[VectorSearchResult] = []
        for document in self.all_documents():
            if where and not self._matches(document.metadata, where):
                continue
            results.append(
                VectorSearchResult(
                    document=document,
                    vector_score=cosine_similarity(
                        query_embedding, document.embedding
                    ),
                )
            )
        results.sort(key=lambda result: result.vector_score, reverse=True)
        return results[:top_k]

    def _matches(self, metadata: dict[str, Any], where: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in where.items())

    def _deserialize(self, row: sqlite3.Row) -> VectorDocument:
        return VectorDocument(
            id=str(row["id"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata_json"]),
            embedding=json.loads(row["embedding_json"]),
        )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def build_vector_store() -> VectorStore:
    settings = get_settings()
    backend = settings.rag_vector_store_backend.strip().lower()
    if backend == "memory":
        return InMemoryVectorStore()
    if backend == "sqlite":
        return SQLiteVectorStore(settings.rag_vector_store_path)
    raise ValueError(f"Unsupported RAG vector store backend: {backend}")


vector_store = build_vector_store()
