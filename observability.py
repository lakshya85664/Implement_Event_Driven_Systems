
"""
Topic 2 - Task 4
Structured event tracing and secret redaction.
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import uuid


SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "token",
    "authorization",
    "credential",
}


def redact_secrets(data):
    """Recursively redact sensitive dictionary fields."""

    if isinstance(data, dict):
        return {
            key: (
                "***REDACTED***"
                if key.lower() in SENSITIVE_KEYS
                else redact_secrets(value)
            )
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [redact_secrets(item) for item in data]

    return data


class WorkflowObserver:

    def __init__(self, trace_file="traces/task4_events.jsonl"):
        self.trace_file = Path(trace_file)
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self.records = []

    def emit(
        self,
        event_type: str,
        run_id: str,
        state: str,
        details=None,
    ):
        record = {
            "trace_id": str(uuid.uuid4()),
            "run_id": run_id,
            "event_type": event_type,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": redact_secrets(details or {}),
        }

        self.records.append(record)

        with self.trace_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

        return record

    def get_trace(self, run_id: str):
        return [
            record for record in self.records
            if record["run_id"] == run_id
        ]

    def get_status(self, run_id: str):
        records = self.get_trace(run_id)

        if not records:
            return {
                "run_id": run_id,
                "state": "unknown",
                "last_event": None,
            }

        latest = records[-1]

        return {
            "run_id": run_id,
            "state": latest["state"],
            "last_event": latest["event_type"],
        }
