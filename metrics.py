
"""
Topic 2 - Task 4
Workflow and dependency metrics.
"""

from collections import defaultdict
from datetime import datetime, timezone


class WorkflowMetrics:

    def __init__(self):
        self.counters = defaultdict(int)
        self.latencies = []
        self.events = []

    def increment(self, metric: str, amount: int = 1):
        self.counters[metric] += amount

    def record_latency(self, operation: str, latency_ms: float):
        if latency_ms < 0:
            raise ValueError("latency cannot be negative")

        self.latencies.append({
            "operation": operation,
            "latency_ms": round(latency_ms, 3),
        })

    def record_event(self, event_type: str):
        self.events.append({
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self.increment(f"events.{event_type}")

    def report(self):
        total_latency = sum(
            item["latency_ms"] for item in self.latencies
        )

        return {
            "counters": dict(self.counters),
            "latency": {
                "measurements": len(self.latencies),
                "total_ms": round(total_latency, 3),
                "average_ms": round(
                    total_latency / len(self.latencies), 3
                ) if self.latencies else 0,
                "max_ms": max(
                    (item["latency_ms"] for item in self.latencies),
                    default=0,
                ),
            },
            "event_count": len(self.events),
        }
