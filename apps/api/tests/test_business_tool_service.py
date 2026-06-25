import pytest

from app.services.business_tool_service import (
    BusinessToolService,
    ToolExecutionError,
)


def test_tool_executor_retries_until_success() -> None:
    service = BusinessToolService(max_attempts=3)
    attempts = 0

    def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    result = service._execute("flaky_tool", flaky_operation)

    assert result.value == "ok"
    assert result.attempts == 3


def test_tool_executor_raises_after_retry_budget() -> None:
    service = BusinessToolService(max_attempts=2)

    with pytest.raises(ToolExecutionError) as error:
        service._execute(
            "failed_tool",
            lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
        )

    assert error.value.tool_name == "failed_tool"
    assert error.value.attempts == 2
