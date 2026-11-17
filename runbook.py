
"""Task 5: Operator runbook and evidence report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
TRACES = ROOT / "traces"
REPORTS = ROOT / "reports"

REQUIRED_EVIDENCE = {
    "task1_contract": OUTPUTS / "task1_contract_output.txt",
    "task2_event_workflow": OUTPUTS / "task2_event_driven_workflow.json",
    "task3_failure_recovery": OUTPUTS / "task3_failure_recovery.json",
    "task3_recovery_trace": TRACES / "task3_recovery_trace.json",
    "task4_observability": OUTPUTS / "task4_observability.json",
    "task4_event_trace": TRACES / "task4_events.jsonl",
}


def inspect_evidence() -> dict[str, Any]:
    """Check that required evidence files exist and are readable."""
    results = {}

    for name, path in REQUIRED_EVIDENCE.items():
        exists = path.is_file()
        readable = False
        size_bytes = 0
        error = None

        if exists:
            try:
                content = path.read_text(encoding="utf-8")
                readable = bool(content.strip())
                size_bytes = path.stat().st_size
            except (OSError, UnicodeError) as exc:
                error = str(exc)

        results[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "exists": exists,
            "readable": readable,
            "size_bytes": size_bytes,
            "error": error,
        }

    return results


def build_evidence_report() -> dict[str, Any]:
    evidence = inspect_evidence()
    total = len(evidence)
    passed = sum(
        item["exists"] and item["readable"]
        for item in evidence.values()
    )

    return {
        "assessment": "Implement Event-Driven Systems",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_summary": {
            "total_required": total,
            "available": passed,
            "missing_or_unreadable": total - passed,
            "complete": passed == total,
        },
        "evidence": evidence,
        "implementation_notes": [
            "The event bus is an in-memory implementation.",
            "Retry backoff is recorded by the retry executor; it is not a production scheduler.",
            "Event deduplication and payment idempotency use in-memory state.",
            "The payment gateway used in the integration demonstration is a fake adapter.",
            "JSONL trace records are appended to the trace file.",
        ],
    }


def generate_operator_runbook() -> str:
    return """# Operator Runbook — Event-Driven Order Fulfillment

## 1. System overview

This project demonstrates an event-driven order fulfillment workflow.
An order producer publishes an `order.validated` event. A payment
consumer processes the order and publishes `payment.completed`.
A shipping consumer reacts to the payment event and creates a shipment.

## 2. Normal workflow

1. Validate the incoming order.
2. Publish the `order.validated` event.
3. Dispatch the event to subscribed consumers.
4. Process payment using an idempotency key.
5. Publish `payment.completed` after successful payment.
6. Create the shipment.
7. Inspect the workflow output and trace records.

## 3. Failure handling

| Failure | Expected operator action |
|---|---|
| Transient dependency error | Allow the configured retry policy to retry |
| Dependency timeout | Check dependency availability and retry outcome |
| Permanent dependency error | Inspect the failure; do not retry blindly |
| Malformed response | Quarantine or investigate the invalid response |
| Retry exhaustion | Review the run and decide whether a controlled replay is safe |
| Duplicate event | Confirm it was rejected by event deduplication |
| Duplicate payment request | Confirm the idempotency key prevents a second side effect |

## 4. Investigation procedure

1. Identify the affected run ID and business order ID.
2. Inspect the corresponding workflow output under `outputs/`.
3. Inspect recovery traces under `traces/`.
4. Check event names, timestamps, and workflow state transitions.
5. Review counters and latency measurements in the observability output.
6. Check whether an event was duplicated, rejected, retried, or quarantined.
7. Record the operator decision before attempting a replay.

## 5. Replay safety

Never replay a payment operation without checking its idempotency key.
Confirm that the business order data matches the original request.
A repeated event ID should be rejected by the deduplication mechanism.
Investigate uncertain payment outcomes before initiating another operation.

## 6. Evidence locations

- `outputs/task1_contract_output.txt`
- `outputs/task2_event_driven_workflow.json`
- `outputs/task3_failure_recovery.json`
- `outputs/task4_observability.json`
- `traces/task3_recovery_trace.json`
- `traces/task4_events.jsonl`

The generated evidence report records which required files are present
and readable.

## 7. Operational limitations

This assessment uses an in-memory event bus and in-memory deduplication
and idempotency state. The fake payment gateway is for testing only.
The implementation does not provide durable message storage, distributed
locking, production authentication, or a persistent recovery database.
A production deployment would require durable infrastructure and
operational monitoring.

## 8. Verification commands

Run the complete test suite:

    python -m pytest -v

Run the demonstrations:

    python event_driven_systems.py
    python orchestrator.py
    python reliability.py
    python adapters.py
    python runbook.py
"""


def generate_reports() -> dict[str, str]:
    REPORTS.mkdir(parents=True, exist_ok=True)

    runbook_path = REPORTS / "OPERATOR_RUNBOOK.md"
    report_path = REPORTS / "evidence_report.json"

    runbook_path.write_text(
        generate_operator_runbook(),
        encoding="utf-8",
    )

    report = build_evidence_report()
    report_path.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    return {
        "runbook": runbook_path.relative_to(ROOT).as_posix(),
        "evidence_report": report_path.relative_to(ROOT).as_posix(),
    }


def main() -> None:
    print("=" * 60)
    print("TASK 5 - OPERATOR RUNBOOK AND EVIDENCE REPORT")
    print("=" * 60)

    generated = generate_reports()
    report = build_evidence_report()

    print(json.dumps(report["evidence_summary"], indent=4))
    print("\nEvidence files:")

    for name, item in report["evidence"].items():
        status = "AVAILABLE" if item["exists"] and item["readable"] else "MISSING"
        print(f"  {name}: {status} ({item['path']})")

    print("\nGenerated reports:")
    for name, path in generated.items():
        print(f"  {name}: {path}")

    if not report["evidence_summary"]["complete"]:
        print("\nWARNING: Some required evidence files are missing or unreadable.")
    else:
        print("\nAll required evidence files are available and readable.")


if __name__ == "__main__":
    main()
