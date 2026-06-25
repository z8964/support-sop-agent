import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402
from app.services.business_tool_service import business_tool_service  # noqa: E402
from app.services.review_service import review_service  # noqa: E402
from app.services.ticket_service import ticket_service  # noqa: E402
from app.services.trace_service import trace_service  # noqa: E402


client = TestClient(app)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Support SOP Agent evals.")
    parser.add_argument(
        "--cases",
        default=str(ROOT / "evals" / "cases"),
        help="Directory containing YAML eval cases.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "evals" / "report.json"),
        help="Path to write JSON report.",
    )
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    results = [run_case(case) for case in cases]
    summary = {
        "total": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
    }
    report = {
        "summary": summary,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


def load_cases(case_dir: Path) -> list[dict[str, Any]]:
    case_files = sorted(case_dir.glob("*.yaml"))
    if not case_files:
        raise FileNotFoundError(f"No YAML cases found in {case_dir}")

    cases = []
    for case_file in case_files:
        with case_file.open("r", encoding="utf-8") as file:
            case = yaml.safe_load(file)
        case["_file"] = str(case_file)
        cases.append(case)
    return cases


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    reset_state()
    failures: list[str] = []

    create_response = client.post("/api/tickets", json=case["input"])
    if create_response.status_code != 201:
        return failed_case(case, [f"ticket_create_status={create_response.status_code}"])

    ticket = create_response.json()
    run_response = client.post(f"/api/tickets/{ticket['id']}/run")
    if run_response.status_code != 200:
        return failed_case(case, [f"workflow_run_status={run_response.status_code}"])

    run_body = run_response.json()
    expected = case["expected"]
    trace_nodes = [step["node"] for step in run_body.get("trace", [])]
    final_reply = run_body.get("final_reply") or ""

    compare_equal(failures, "intent", run_body.get("intent"), expected.get("intent"))
    compare_equal(failures, "status", run_body.get("status"), expected.get("status"))
    compare_equal(
        failures,
        "risk_level",
        run_body.get("risk_level"),
        expected.get("risk_level"),
    )
    compare_equal(
        failures,
        "need_human_review",
        run_body.get("need_human_review"),
        expected.get("need_human_review"),
    )
    compare_equal(
        failures,
        "decision",
        run_body.get("decision", {}).get("decision"),
        expected.get("decision"),
    )

    for node in expected.get("tools_called", []):
        if node not in trace_nodes:
            failures.append(f"expected trace node missing: {node}")

    for text in expected.get("should_include", []):
        if text not in final_reply:
            failures.append(f"final_reply should include: {text}")

    for text in expected.get("should_not_include", []):
        if text in final_reply:
            failures.append(f"final_reply should not include: {text}")

    scores = {
        "intent_accuracy": int(not has_failure(failures, "intent")),
        "workflow_status": int(not has_failure(failures, "status")),
        "risk_control": int(
            not has_failure(failures, "risk_level")
            and not has_failure(failures, "need_human_review")
        ),
        "decision_accuracy": int(not has_failure(failures, "decision")),
        "reply_policy": int(
            not any("final_reply" in failure for failure in failures)
        ),
        "trace_completeness": int(
            not any("trace node" in failure for failure in failures)
        ),
    }

    return {
        "case_id": case["case_id"],
        "name": case.get("name"),
        "passed": not failures,
        "scores": scores,
        "failures": failures,
        "ticket_id": ticket["id"],
        "trace_nodes": trace_nodes,
    }


def reset_state() -> None:
    ticket_service.reset()
    trace_service.reset()
    review_service.reset()
    business_tool_service.reset()


def compare_equal(
    failures: list[str],
    field: str,
    actual: Any,
    expected: Any,
) -> None:
    if expected is None:
        return
    if actual != expected:
        failures.append(f"{field}: expected {expected!r}, got {actual!r}")


def has_failure(failures: list[str], field: str) -> bool:
    return any(failure.startswith(f"{field}:") for failure in failures)


def failed_case(case: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "name": case.get("name"),
        "passed": False,
        "scores": {},
        "failures": failures,
    }


if __name__ == "__main__":
    raise SystemExit(main())
