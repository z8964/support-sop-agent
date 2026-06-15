from app.schemas.memory import MemoryCreate, MemoryListResponse, MemoryRecord, utc_now


class MemoryService:
    def __init__(self) -> None:
        self._records_by_user: dict[str, list[MemoryRecord]] = {}
        self._counter = 0
        self._seed_defaults()

    def create_memory(self, payload: MemoryCreate) -> MemoryRecord:
        self._counter += 1
        record = MemoryRecord(
            id=f"M{self._counter:08d}",
            user_id=payload.user_id,
            type=payload.type,
            content=payload.content,
            metadata=payload.metadata,
            created_at=utc_now(),
        )
        self._records_by_user.setdefault(payload.user_id, []).append(record)
        return record

    def list_user_memories(
        self,
        user_id: str,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> MemoryListResponse:
        records = list(self._records_by_user.get(user_id, []))
        if memory_type:
            records = [record for record in records if record.type == memory_type]

        records.sort(key=lambda record: record.created_at, reverse=True)
        page = records[:limit]
        return MemoryListResponse(user_id=user_id, items=page, total=len(records))

    def build_user_context(self, user_id: str) -> dict:
        memories = self.list_user_memories(user_id=user_id, limit=5).items
        return {
            "memories": [memory.model_dump(mode="json") for memory in memories],
            "summary": self._summarize(memories),
        }

    def write_workflow_outcome(
        self,
        user_id: str,
        ticket_id: str,
        intent: str,
        status: str,
        decision: str,
    ) -> MemoryRecord:
        return self.create_memory(
            MemoryCreate(
                user_id=user_id,
                type="workflow_outcome",
                content=(
                    f"Ticket {ticket_id} was handled as {intent}; "
                    f"decision={decision}; status={status}."
                ),
                metadata={
                    "ticket_id": ticket_id,
                    "intent": intent,
                    "status": status,
                    "decision": decision,
                },
            )
        )

    def reset(self) -> None:
        self._records_by_user.clear()
        self._counter = 0
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        self.create_memory(
            MemoryCreate(
                user_id="U1003",
                type="user_preference",
                content="VIP customer prefers careful manual confirmation for refund decisions.",
                metadata={"source": "seed"},
            )
        )
        self.create_memory(
            MemoryCreate(
                user_id="U1005",
                type="user_preference",
                content="Enterprise customer often needs formal invoice wording.",
                metadata={"source": "seed"},
            )
        )

    def _summarize(self, memories: list[MemoryRecord]) -> str:
        if not memories:
            return "No memory available for this user."
        return " ".join(memory.content for memory in memories)


memory_service = MemoryService()

