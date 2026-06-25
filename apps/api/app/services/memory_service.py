import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas.memory import (
    MemoryCreate,
    MemoryListResponse,
    MemoryRecord,
    MemoryRetrieveResponse,
    MemorySearchHit,
    utc_now,
)


class MemoryNotFoundError(Exception):
    pass


class MemoryService:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(
            database_path or get_settings().memory_store_path
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if self._count_all() == 0:
            self._seed_defaults()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    importance REAL NOT NULL,
                    memory_key TEXT,
                    status TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_user_status
                ON memories (user_id, status)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_user_key
                ON memories (user_id, memory_key)
                """
            )

    def create_memory(self, payload: MemoryCreate) -> MemoryRecord:
        now = utc_now()
        duplicate = self._find_exact_duplicate(payload)
        if duplicate:
            return duplicate

        if payload.memory_key:
            self._supersede_active_key(
                user_id=payload.user_id,
                memory_key=payload.memory_key,
                updated_at=now,
            )

        record = MemoryRecord(
            id=self._next_id(),
            user_id=payload.user_id,
            type=payload.type,
            content=payload.content.strip(),
            metadata=payload.metadata,
            scope=payload.scope,
            source=payload.source,
            confidence=payload.confidence,
            importance=payload.importance,
            memory_key=payload.memory_key,
            expires_at=payload.expires_at,
            created_at=now,
            updated_at=now,
        )
        self._insert(record)
        return record

    def list_user_memories(
        self,
        user_id: str,
        limit: int = 10,
        memory_type: str | None = None,
        include_inactive: bool = False,
    ) -> MemoryListResponse:
        clauses = ["user_id = ?"]
        parameters: list[Any] = [user_id]
        if memory_type:
            clauses.append("type = ?")
            parameters.append(memory_type)
        if not include_inactive:
            clauses.append("status = 'active'")

        query = (
            "SELECT * FROM memories WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC"
        )
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        records = [
            record
            for record in (self._deserialize(row) for row in rows)
            if include_inactive or not self._is_expired(record)
        ]
        return MemoryListResponse(
            user_id=user_id,
            items=records[:limit],
            total=len(records),
        )

    def retrieve(
        self,
        user_id: str,
        query: str,
        intent: str | None = None,
        top_k: int | None = None,
    ) -> MemoryRetrieveResponse:
        settings = get_settings()
        candidates = self.list_user_memories(
            user_id=user_id,
            limit=100,
        ).items
        query_terms = self._tokenize(f"{query} {intent or ''}")
        scored: list[MemorySearchHit] = []

        for memory in candidates:
            if memory.confidence < settings.memory_min_confidence:
                continue
            memory_terms = self._tokenize(
                " ".join(
                    [
                        memory.content,
                        memory.type,
                        memory.scope,
                        json.dumps(memory.metadata, ensure_ascii=False),
                    ]
                )
            )
            matched_terms = sorted(query_terms.intersection(memory_terms))
            intent_matches = bool(
                intent and memory.metadata.get("intent") == intent
            )
            if (
                not matched_terms
                and not intent_matches
                and memory.type != "risk_signal"
            ):
                continue
            score = self._relevance_score(
                memory=memory,
                matched_terms=matched_terms,
                query_terms=query_terms,
                intent=intent,
            )
            if score > 0:
                scored.append(
                    MemorySearchHit(
                        memory=memory,
                        score=round(score, 4),
                        matched_terms=matched_terms,
                    )
                )

        scored.sort(
            key=lambda hit: (
                hit.score,
                hit.memory.updated_at,
            ),
            reverse=True,
        )
        selected = scored[: top_k or settings.memory_retrieval_top_k]
        self._touch([hit.memory.id for hit in selected])
        return MemoryRetrieveResponse(
            user_id=user_id,
            query=query,
            hits=selected,
            summary=self._summarize([hit.memory for hit in selected]),
        )

    def build_user_context(
        self,
        user_id: str,
        query: str = "",
        intent: str | None = None,
    ) -> dict[str, Any]:
        retrieval = self.retrieve(
            user_id=user_id,
            query=query or intent or "user context",
            intent=intent,
        )
        grouped: dict[str, list[dict[str, Any]]] = {
            "semantic": [],
            "episodic": [],
            "procedural": [],
        }
        for hit in retrieval.hits:
            grouped[hit.memory.scope].append(
                {
                    **hit.memory.model_dump(mode="json"),
                    "retrieval_score": hit.score,
                }
            )
        return {
            "memories": [
                {
                    **hit.memory.model_dump(mode="json"),
                    "retrieval_score": hit.score,
                    "matched_terms": hit.matched_terms,
                }
                for hit in retrieval.hits
            ],
            "by_scope": grouped,
            "summary": retrieval.summary,
        }

    def forget_memory(self, memory_id: str) -> MemoryRecord:
        record = self._get(memory_id)
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE memories
                SET status = 'deleted', updated_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), memory_id),
            )
        return record.model_copy(update={"status": "deleted", "updated_at": now})

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
                scope="episodic",
                source="agent_workflow",
                confidence=1.0,
                importance=0.6,
                memory_key=f"workflow:{ticket_id}",
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
        with self._connect() as connection:
            connection.execute("DELETE FROM memories")
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        self.create_memory(
            MemoryCreate(
                user_id="U1003",
                type="user_preference",
                scope="semantic",
                source="seed",
                confidence=0.95,
                importance=0.9,
                memory_key="refund_review_preference",
                content=(
                    "VIP customer prefers careful manual confirmation "
                    "for refund decisions."
                ),
                metadata={"intent": "refund_request"},
            )
        )
        self.create_memory(
            MemoryCreate(
                user_id="U1005",
                type="user_preference",
                scope="semantic",
                source="seed",
                confidence=0.9,
                importance=0.7,
                memory_key="invoice_wording_preference",
                content="Enterprise customer often needs formal invoice wording.",
                metadata={"intent": "invoice_request"},
            )
        )

    def _insert(self, record: MemoryRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id, user_id, type, content, metadata_json, scope, source,
                    confidence, importance, memory_key, status, expires_at,
                    created_at, updated_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.user_id,
                    record.type,
                    record.content,
                    json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
                    record.scope,
                    record.source,
                    record.confidence,
                    record.importance,
                    record.memory_key,
                    record.status,
                    self._serialize_datetime(record.expires_at),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    self._serialize_datetime(record.last_accessed_at),
                ),
            )

    def _find_exact_duplicate(self, payload: MemoryCreate) -> MemoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM memories
                WHERE user_id = ? AND type = ? AND content = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
                """,
                (payload.user_id, payload.type, payload.content.strip()),
            ).fetchone()
        return self._deserialize(row) if row else None

    def _supersede_active_key(
        self,
        user_id: str,
        memory_key: str,
        updated_at: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE memories
                SET status = 'superseded', updated_at = ?
                WHERE user_id = ? AND memory_key = ? AND status = 'active'
                """,
                (updated_at.isoformat(), user_id, memory_key),
            )

    def _get(self, memory_id: str) -> MemoryRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(memory_id)
        return self._deserialize(row)

    def _touch(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.executemany(
                "UPDATE memories SET last_accessed_at = ? WHERE id = ?",
                [(now, memory_id) for memory_id in memory_ids],
            )

    def _next_id(self) -> str:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM memories").fetchall()
        highest = max((int(str(row["id"])[1:]) for row in rows), default=0)
        return f"M{highest + 1:08d}"

    def _count_all(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS record_count FROM memories"
            ).fetchone()
        return int(row["record_count"])

    def _deserialize(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            type=str(row["type"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata_json"]),
            scope=str(row["scope"]),
            source=str(row["source"]),
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            memory_key=row["memory_key"],
            status=str(row["status"]),
            expires_at=self._parse_datetime(row["expires_at"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
            last_accessed_at=self._parse_datetime(row["last_accessed_at"]),
        )

    def _is_expired(self, record: MemoryRecord) -> bool:
        if not record.expires_at:
            return False
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    def _relevance_score(
        self,
        memory: MemoryRecord,
        matched_terms: list[str],
        query_terms: set[str],
        intent: str | None,
    ) -> float:
        coverage = len(matched_terms) / max(len(query_terms), 1)
        intent_match = 0.0
        if intent and memory.metadata.get("intent") == intent:
            intent_match = 0.35
        always_relevant = 0.2 if memory.type == "risk_signal" else 0.0
        recency = self._recency_score(memory.updated_at)
        return (
            coverage * 0.35
            + memory.confidence * 0.2
            + memory.importance * 0.15
            + recency * 0.1
            + intent_match
            + always_relevant
        )

    def _recency_score(self, updated_at: datetime) -> float:
        age_days = max(
            (datetime.now(timezone.utc) - updated_at).total_seconds() / 86400,
            0,
        )
        return 1.0 / (1.0 + age_days / 30.0)

    def _tokenize(self, text: str) -> set[str]:
        normalized = text.lower()
        latin = {
            token
            for token in re.findall(r"[a-z0-9_]+", normalized)
            if len(token) > 1
        }
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        cjk_bigrams = {
            "".join(cjk_chars[index : index + 2])
            for index in range(max(len(cjk_chars) - 1, 0))
        }
        return latin.union(cjk_chars).union(cjk_bigrams)

    def _summarize(self, memories: list[MemoryRecord]) -> str:
        if not memories:
            return "No relevant memory available for this ticket."
        labels = {
            "semantic": "Stable user context",
            "episodic": "Relevant history",
            "procedural": "Successful handling strategy",
        }
        sections: list[str] = []
        for scope in ("semantic", "episodic", "procedural"):
            contents = [
                memory.content for memory in memories if memory.scope == scope
            ]
            if contents:
                sections.append(f"{labels[scope]}: {' '.join(contents)}")
        return "\n".join(sections)

    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None


memory_service = MemoryService()
