import pytest

from app.schemas.mock import EscalationCreate
from app.services.business_tool_service import (
    BusinessToolService,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)
from app.services.mock_data import ESCALATIONS


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


def test_gateway_rejects_missing_permission(tmp_path) -> None:
    service = BusinessToolService(
        database_path=tmp_path / "tools.sqlite3"
    )

    with pytest.raises(ToolPermissionError, match="order:read"):
        service.execute(
            "get_order",
            {"order_id": "OD2026001"},
            actor="untrusted_agent",
            permissions=set(),
        )

    audit = service.list_audits().items[0]
    assert audit.status == "denied"
    assert audit.actor == "untrusted_agent"


def test_gateway_validates_input_before_execution(tmp_path) -> None:
    service = BusinessToolService(
        database_path=tmp_path / "tools.sqlite3"
    )

    with pytest.raises(ToolValidationError):
        service.execute(
            "get_order",
            {"order_id": ""},
            actor="ticket_agent",
            permissions={"order:read"},
        )

    assert service.list_audits().items[0].status == "invalid"


def test_write_tool_requires_idempotency_key(tmp_path) -> None:
    service = BusinessToolService(
        database_path=tmp_path / "tools.sqlite3"
    )

    with pytest.raises(ToolValidationError, match="idempotency"):
        service.execute(
            "create_escalation",
            {
                "ticket_id": "T00000001",
                "reason": "high_value_refund",
                "risk_level": "high",
            },
            actor="ticket_agent",
            permissions={"escalation:write"},
        )


def test_write_tool_replays_idempotent_result(tmp_path) -> None:
    ESCALATIONS.clear()
    service = BusinessToolService(
        database_path=tmp_path / "tools.sqlite3"
    )
    payload = EscalationCreate(
        ticket_id="T00000001",
        reason="high_value_refund",
        risk_level="high",
    )

    first = service.create_escalation(payload, "ticket:T00000001:escalation")
    second = service.create_escalation(payload, "ticket:T00000001:escalation")

    assert len(ESCALATIONS) == 1
    assert first.value == second.value
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert second.attempts == 0


def test_audit_redacts_sensitive_arguments(tmp_path) -> None:
    service = BusinessToolService(
        database_path=tmp_path / "tools.sqlite3"
    )

    service._save_audit(
        tool_name="external_api",
        actor="ticket_agent",
        permission="external:read",
        status="success",
        arguments={
            "order_id": "OD2026001",
            "authorization": "Bearer secret",
            "nested": {"api_key": "secret-key"},
        },
        attempts=1,
        duration_ms=1.0,
    )

    audit = service.list_audits().items[0]
    assert audit.arguments["authorization"] == "[REDACTED]"
    assert audit.arguments["nested"]["api_key"] == "[REDACTED]"
