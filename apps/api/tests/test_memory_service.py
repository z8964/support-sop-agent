from datetime import timedelta
from pathlib import Path

from app.schemas.memory import MemoryCreate, utc_now
from app.services.memory_service import MemoryService


def test_memory_service_persists_records(tmp_path: Path) -> None:
    database_path = tmp_path / "memories.sqlite3"
    service = MemoryService(database_path)
    service.reset()
    created = service.create_memory(
        MemoryCreate(
            user_id="U3001",
            type="business_fact",
            content="Account verification completed.",
            memory_key="account_verification",
        )
    )

    restored = MemoryService(database_path)

    assert restored.list_user_memories("U3001").items[0].id == created.id


def test_same_memory_key_supersedes_previous_value(tmp_path: Path) -> None:
    service = MemoryService(tmp_path / "memories.sqlite3")
    service.reset()
    old = service.create_memory(
        MemoryCreate(
            user_id="U3001",
            type="business_fact",
            content="Preferred language is English.",
            memory_key="preferred_language",
        )
    )
    new = service.create_memory(
        MemoryCreate(
            user_id="U3001",
            type="business_fact",
            content="Preferred language is Chinese.",
            memory_key="preferred_language",
        )
    )

    active = service.list_user_memories("U3001")
    all_records = service.list_user_memories(
        "U3001",
        include_inactive=True,
    )

    assert active.total == 1
    assert active.items[0].id == new.id
    assert {record.id: record.status for record in all_records.items} == {
        new.id: "active",
        old.id: "superseded",
    }


def test_duplicate_memory_is_not_written_twice(tmp_path: Path) -> None:
    service = MemoryService(tmp_path / "memories.sqlite3")
    service.reset()
    payload = MemoryCreate(
        user_id="U3001",
        type="user_preference",
        content="Customer prefers concise replies.",
    )

    first = service.create_memory(payload)
    second = service.create_memory(payload)

    assert first.id == second.id
    assert service.list_user_memories("U3001").total == 1


def test_expired_and_low_confidence_memories_are_not_retrieved(
    tmp_path: Path,
) -> None:
    service = MemoryService(tmp_path / "memories.sqlite3")
    service.reset()
    service.create_memory(
        MemoryCreate(
            user_id="U3001",
            type="risk_signal",
            content="Refund activity requires manual review.",
            expires_at=utc_now() - timedelta(days=1),
        )
    )
    service.create_memory(
        MemoryCreate(
            user_id="U3001",
            type="risk_signal",
            content="Refund activity may require manual review.",
            confidence=0.2,
        )
    )

    result = service.retrieve(
        user_id="U3001",
        query="refund request",
        intent="refund_request",
    )

    assert result.hits == []
