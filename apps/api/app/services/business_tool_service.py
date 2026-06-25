from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from app.config import get_settings
from app.services.mock_data import LOGISTICS, ORDERS, TICKET_HISTORY, USERS


T = TypeVar("T")


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    value: Any
    attempts: int


class ToolExecutionError(RuntimeError):
    def __init__(self, tool_name: str, attempts: int, cause: Exception) -> None:
        super().__init__(f"{tool_name} failed after {attempts} attempts: {cause}")
        self.tool_name = tool_name
        self.attempts = attempts
        self.cause = cause


class BusinessToolService:
    def __init__(self, max_attempts: int | None = None) -> None:
        configured_attempts = get_settings().agent_tool_max_attempts
        self.max_attempts = max(max_attempts or configured_attempts, 1)

    def get_user(self, user_id: str) -> ToolResult:
        return self._execute(
            "get_user",
            lambda: USERS.get(user_id).model_dump() if user_id in USERS else None,
        )

    def get_ticket_history(self, user_id: str) -> ToolResult:
        return self._execute(
            "get_ticket_history",
            lambda: [
                item.model_dump() for item in TICKET_HISTORY.get(user_id, [])
            ],
        )

    def get_order(self, order_id: str) -> ToolResult:
        return self._execute(
            "get_order",
            lambda: ORDERS.get(order_id).model_dump() if order_id in ORDERS else None,
        )

    def get_logistics(self, order_id: str) -> ToolResult:
        return self._execute(
            "get_logistics",
            lambda: (
                LOGISTICS.get(order_id).model_dump()
                if order_id in LOGISTICS
                else None
            ),
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


business_tool_service = BusinessToolService()
