from pathlib import Path

from app.services.vector_store import SQLiteVectorStore, VectorDocument


def test_sqlite_vector_store_persists_documents(tmp_path: Path) -> None:
    database_path = tmp_path / "vectors.sqlite3"
    store = SQLiteVectorStore(database_path)
    store.upsert(
        [
            VectorDocument(
                id="refund_001",
                content="A shipped order requires manual refund review.",
                metadata={"policy_type": "refund", "section": "Shipped Orders"},
                embedding=[1.0, 0.0, 0.0],
            )
        ]
    )
    store.set_index_metadata(
        {
            "knowledge_signature": "knowledge-v1",
            "embedding_signature": "hash:test:3",
        }
    )

    restored_store = SQLiteVectorStore(database_path)

    assert restored_store.count() == 1
    assert restored_store.get_index_metadata()["knowledge_signature"] == "knowledge-v1"
    assert restored_store.all_documents()[0].id == "refund_001"


def test_sqlite_vector_store_searches_and_filters(tmp_path: Path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    store.upsert(
        [
            VectorDocument(
                id="refund_001",
                content="Refund policy",
                metadata={"policy_type": "refund"},
                embedding=[1.0, 0.0],
            ),
            VectorDocument(
                id="invoice_001",
                content="Invoice policy",
                metadata={"policy_type": "invoice"},
                embedding=[0.0, 1.0],
            ),
        ]
    )

    results = store.search(
        query_embedding=[1.0, 0.0],
        top_k=2,
        where={"policy_type": "refund"},
    )

    assert [result.document.id for result in results] == ["refund_001"]
    assert results[0].vector_score == 1.0
