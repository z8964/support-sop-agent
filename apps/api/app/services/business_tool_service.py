import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.config import get_settings
from app.schemas.mock import (
    EscalationCreate,
    MockEscalation,
    MockLogistics,
    MockOrder,
    MockTicketHistoryItem,
    MockUser,
)
from app.schemas.tool import (
    OrderLookupInput,
    ToolAuditListResponse,
    ToolAuditRecord,
    UserLookupInput,
)
from app.services.mock_data import (
    LOGISTICS,
    ORDERS,
    TICKET_HISTORY,
    USERS,
    create_escalation,
)


T = TypeVar("T")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    input_model: type[BaseModel]
    output_type: Any
    permission: str
    side_effect: bool
    handler: Callable[[BaseModel], Any]


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    value: Any
    attempts: int
    audit_id: str | None = None
    idempotent_replay: bool = False


class ToolExecutionError(RuntimeError):
    def __init__(self, tool_name: str, attempts: int, cause: Exception) -> None:
        super().__init__(f"{tool_name} failed after {attempts} attempts: {cause}")
        self.tool_name = tool_name
        self.attempts = attempts
        self.cause = cause


class ToolPermissionError(PermissionError):
    pass


class ToolValidationError(ValueError):
    pass


class BusinessToolService:
    def __init__(
        self,
        max_attempts: int | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.max_attempts = max(
            max_attempts or settings.agent_tool_max_attempts,
            1,
        )
        self.database_path = Path(database_path or settings.tool_store_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._definitions = self._build_definitions()

    def get_user(self, user_id: str) -> ToolResult:
        return self.execute(
            "get_user",
            {"user_id": user_id},
            actor="ticket_agent",
            permissions={"customer:read"},
        )

    def get_ticket_history(self, user_id: str) -> ToolResult:
        return self.execute(
            "get_ticket_history",
            {"user_id": user_id},
            actor="ticket_agent",
            permissions={"ticket_history:read"},
        )

    def get_order(self, order_id: str) -> ToolResult:
        return self.execute(
            "get_order",
            {"order_id": order_id},
            actor="ticket_agent",
            permissions={"order:read"},
        )

    def get_logistics(self, order_id: str) -> ToolResult:
        return self.execute(
            "get_logistics",
            {"order_id": order_id},
            actor="ticket_agent",
            permissions={"logistics:read"},
        )

    def create_escalation(
        self,
        payload: EscalationCreate,
        idempotency_key: str,
    ) -> ToolResult:
        return self.execute(
            "create_escalation",
            payload.model_dump(),
            actor="ticket_agent",
            permissions={"escalation:write"},
            idempotency_key=idempotency_key,
        )

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        actor: str,
        permissions: set[str],
        idempotency_key: str | None = None,
    ) -> ToolResult:
        definition = self._definitions.get(tool_name)
        if definition is None:
            raise ToolValidationError(f"Unknown tool: {tool_name}")

        started_at = time.perf_counter()
        try:
            validated_input = definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            self._save_audit(
                tool_name=tool_name,
                actor=actor,
                permission=definition.permission,
                status="invalid",
                arguments=arguments,
                error=str(exc),
                attempts=0,
                duration_ms=self._duration_ms(started_at),
                idempotency_key=idempotency_key,
            )
            raise ToolValidationError(str(exc)) from exc

        if definition.permission not in permissions:
            error = f"Missing permission: {definition.permission}"
            self._save_audit(
                tool_name=tool_name,
                actor=actor,
                permission=definition.permission,
                status="denied",
                arguments=arguments,
                error=error,
                attempts=0,
                duration_ms=self._duration_ms(started_at),
                idempotency_key=idempotency_key,
            )
            raise ToolPermissionError(error)

        if definition.side_effect and not idempotency_key:
            error = "Side-effecting tools require an idempotency key"
            self._save_audit(
                tool_name=tool_name,
                actor=actor,
                permission=definition.permission,
                status="invalid",
                arguments=arguments,
                error=error,
                attempts=0,
                duration_ms=self._duration_ms(started_at),
            )
            raise ToolValidationError(error)

        if idempotency_key:
            replay = self._get_idempotent_result(tool_name, idempotency_key)
            if replay is not None:
                value = TypeAdapter(definition.output_type).validate_python(replay)
                audit = self._save_audit(
                    tool_name=tool_name,
                    actor=actor,
                    permission=definition.permission,
                    status="success",
                    arguments=arguments,
                    result=self._dump_value(value),
                    attempts=0,
                    duration_ms=self._duration_ms(started_at),
                    idempotency_key=idempotency_key,
                    idempotent_replay=True,
                )
                return ToolResult(
                    tool_name=tool_name,
                    value=self._dump_value(value),
                    attempts=0,
                    audit_id=audit.audit_id,
                    idempotent_replay=True,
                )

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw_value = definition.handler(validated_input)
                validated_output = TypeAdapter(
                    definition.output_type
                ).validate_python(raw_value)
                value = self._dump_value(validated_output)
                if idempotency_key:
                    self._save_idempotent_result(
                        tool_name,
                        idempotency_key,
                        value,
                    )
                audit = self._save_audit(
                    tool_name=tool_name,
                    actor=actor,
                    permission=definition.permission,
                    status="success",
                    arguments=arguments,
                    result=value,
                    attempts=attempt,
                    duration_ms=self._duration_ms(started_at),
                    idempotency_key=idempotency_key,
                )
                return ToolResult(
                    tool_name=tool_name,
                    value=value,
                    attempts=attempt,
                    audit_id=audit.audit_id,
                )
            except Exception as exc:
                last_error = exc

        assert last_error is not None
        self._save_audit(
            tool_name=tool_name,
            actor=actor,
            permission=definition.permission,
            status="failed",
            arguments=arguments,
            error=str(last_error),
            attempts=self.max_attempts,
            duration_ms=self._duration_ms(started_at),
            idempotency_key=idempotency_key,
        )
        raise ToolExecutionError(
            tool_name,
            self.max_attempts,
            last_error,
        )

    def _execute(self, tool_name: str, operation: Callable[[], T]) -> ToolResult:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return ToolResult(
                    tool_name=tool_name,
                    value=operation(),
                    attempts=attempt,
                )
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise ToolExecutionError(tool_name, self.max_attempts, last_error)

    def list_audits(
        self,
        limit: int = 50,
        tool_name: str | None = None,
        status: str | None = None,
    ) -> ToolAuditListResponse:
        clauses: list[str] = []
        parameters: list[Any] = []
        if tool_name:
            clauses.append("tool_name = ?")
            parameters.append(tool_name)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM tool_audits
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*parameters, limit],
            ).fetchall()
            count = connection.execute(
                f"SELECT COUNT(*) AS total FROM tool_audits {where}",
                parameters,
            ).fetchone()
        return ToolAuditListResponse(
            items=[self._deserialize_audit(row) for row in rows],
            total=int(count["total"]),
        )

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM tool_audits")
            connection.execute("DELETE FROM tool_idempotency")

    def _build_definitions(self) -> dict[str, ToolDefinition]:
        return {
            "get_user": ToolDefinition(
                name="get_user",
                input_model=UserLookupInput,
                output_type=MockUser | None,
                permission="customer:read",
                side_effect=False,
                handler=lambda payload: USERS.get(payload.user_id),
            ),
            "get_ticket_history": ToolDefinition(
                name="get_ticket_history",
                input_model=UserLookupInput,
                output_type=list[MockTicketHistoryItem],
                permission="ticket_history:read",
                side_effect=False,
                handler=lambda payload: TICKET_HISTORY.get(payload.user_id, []),
            ),
            "get_order": ToolDefinition(
                name="get_order",
                input_model=OrderLookupInput,
                output_type=MockOrder | None,
                permission="order:read",
                side_effect=False,
                handler=lambda payload: ORDERS.get(payload.order_id),
            ),
            "get_logistics": ToolDefinition(
                name="get_logistics",
                input_model=OrderLookupInput,
                output_type=MockLogistics | None,
                permission="logistics:read",
                side_effect=False,
                handler=lambda payload: LOGISTICS.get(payload.order_id),
            ),
            "create_escalation": ToolDefinition(
                name="create_escalation",
                input_model=EscalationCreate,
                output_type=MockEscalation,
                permission="escalation:write",
                side_effect=True,
                handler=lambda payload: create_escalation(payload),
            ),
        }

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_audits (
                    audit_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    status TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL,
                    duration_ms REAL NOT NULL,
                    idempotency_key TEXT,
                    idempotent_replay INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_idempotency (
                    tool_name TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tool_name, idempotency_key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _save_audit(
        self,
        *,
        tool_name: str,
        actor: str,
        permission: str,
        status: str,
        arguments: dict[str, Any],
        result: Any = None,
        error: str | None = None,
        attempts: int,
        duration_ms: float,
        idempotency_key: str | None = None,
        idempotent_replay: bool = False,
    ) -> ToolAuditRecord:
        created_at = datetime.now(timezone.utc)
        safe_arguments = self._redact_sensitive(arguments)
        safe_result = self._redact_sensitive(result)
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM tool_audits"
            ).fetchone()
            audit_id = f"TA{int(count['total']) + 1:08d}"
            connection.execute(
                """
                INSERT INTO tool_audits (
                    audit_id, tool_name, actor, permission, status,
                    arguments_json, result_json, error, attempts, duration_ms,
                    idempotency_key, idempotent_replay, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    tool_name,
                    actor,
                    permission,
                    status,
                    json.dumps(safe_arguments, ensure_ascii=False, sort_keys=True),
                    (
                        json.dumps(safe_result, ensure_ascii=False, sort_keys=True)
                        if safe_result is not None
                        else None
                    ),
                    error,
                    attempts,
                    duration_ms,
                    idempotency_key,
                    int(idempotent_replay),
                    created_at.isoformat(),
                ),
            )
        return ToolAuditRecord(
            audit_id=audit_id,
            tool_name=tool_name,
            actor=actor,
            permission=permission,
            status=status,
            arguments=safe_arguments,
            result=safe_result,
            error=error,
            attempts=attempts,
            duration_ms=duration_ms,
            idempotency_key=idempotency_key,
            idempotent_replay=idempotent_replay,
            created_at=created_at,
        )

    def _get_idempotent_result(
        self,
        tool_name: str,
        idempotency_key: str,
    ) -> Any | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT result_json FROM tool_idempotency
                WHERE tool_name = ? AND idempotency_key = ?
                """,
                (tool_name, idempotency_key),
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def _save_idempotent_result(
        self,
        tool_name: str,
        idempotency_key: str,
        result: Any,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO tool_idempotency (
                    tool_name, idempotency_key, result_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    tool_name,
                    idempotency_key,
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def _deserialize_audit(self, row: sqlite3.Row) -> ToolAuditRecord:
        return ToolAuditRecord(
            audit_id=str(row["audit_id"]),
            tool_name=str(row["tool_name"]),
            actor=str(row["actor"]),
            permission=str(row["permission"]),
            status=str(row["status"]),
            arguments=json.loads(row["arguments_json"]),
            result=(
                json.loads(row["result_json"])
                if row["result_json"] is not None
                else None
            ),
            error=row["error"],
            attempts=int(row["attempts"]),
            duration_ms=float(row["duration_ms"]),
            idempotency_key=row["idempotency_key"],
            idempotent_replay=bool(row["idempotent_replay"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _dump_value(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [self._dump_value(item) for item in value]
        return value

    def _duration_ms(self, started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 3)

    def _redact_sensitive(self, value: Any) -> Any:
        sensitive_keys = {
            "api_key",
            "authorization",
            "password",
            "secret",
            "token",
        }
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if key.lower() in sensitive_keys
                    else self._redact_sensitive(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_sensitive(item) for item in value]
        return value


business_tool_service = BusinessToolService()
