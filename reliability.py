
"""
Topic 2 - Task 3
Failure, Retry and Replay Safety

Features:
- Error classification
- Bounded retry execution
- Retry trace and explicit next action
- Event ID deduplication
- Business-operation idempotency
- Duplicate delivery protection
- Failure fixtures and recovery demonstration
"""

from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------
# 1. ERROR CLASSIFICATION
# ---------------------------------------------------------

class TransientDependencyError(Exception):
    """Temporary dependency failure that may be retried."""


class PermanentDependencyError(Exception):
    """Permanent dependency failure; do not retry."""


class DependencyTimeout(Exception):
    """Dependency exceeded its permitted time."""


class MalformedResponseError(Exception):
    """Dependency returned an invalid response."""


# ---------------------------------------------------------
# 2. RETRY POLICY
# ---------------------------------------------------------

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 4.0

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if self.initial_backoff < 0:
            raise ValueError("initial_backoff cannot be negative")

        if self.max_backoff < self.initial_backoff:
            raise ValueError(
                "max_backoff must be >= initial_backoff"
            )

    def backoff_for(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        delay = self.initial_backoff * (2 ** (attempt - 1))

        return min(delay, self.max_backoff)


# ---------------------------------------------------------
# 3. RETRY RESULT
# ---------------------------------------------------------

@dataclass
class RetryResult:
    success: bool
    attempts: int
    result: Any = None
    error_type: str | None = None
    error: str | None = None
    next_action: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------
# 4. RETRY EXECUTOR
# ---------------------------------------------------------

class RetryExecutor:

    RETRYABLE_ERRORS = (
        TransientDependencyError,
        DependencyTimeout,
    )

    def __init__(self, policy: RetryPolicy | None = None):
        self.policy = policy or RetryPolicy()

    def execute(self, operation: Callable[[], Any]) -> RetryResult:

        trace = []

        for attempt in range(1, self.policy.max_attempts + 1):

            try:
                result = operation()

                trace.append({
                    "attempt": attempt,
                    "outcome": "success",
                    "next_action": "continue",
                })

                return RetryResult(
                    success=True,
                    attempts=attempt,
                    result=result,
                    next_action="continue_workflow",
                    trace=trace,
                )

            except self.RETRYABLE_ERRORS as exc:

                final_attempt = (
                    attempt == self.policy.max_attempts
                )

                backoff = (
                    None
                    if final_attempt
                    else self.policy.backoff_for(attempt)
                )

                trace.append({
                    "attempt": attempt,
                    "outcome": "retryable_failure",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "backoff_seconds": backoff,
                    "next_action": (
                        "operator_review"
                        if final_attempt
                        else "retry"
                    ),
                })

                if final_attempt:
                    return RetryResult(
                        success=False,
                        attempts=attempt,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        next_action="operator_review",
                        trace=trace,
                    )

            except (
                PermanentDependencyError,
                MalformedResponseError,
            ) as exc:

                trace.append({
                    "attempt": attempt,
                    "outcome": "non_retryable_failure",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "backoff_seconds": None,
                    "next_action": "quarantine_and_review",
                })

                return RetryResult(
                    success=False,
                    attempts=attempt,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    next_action="quarantine_and_review",
                    trace=trace,
                )

            except Exception as exc:

                trace.append({
                    "attempt": attempt,
                    "outcome": "unexpected_failure",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "next_action": "operator_review",
                })

                return RetryResult(
                    success=False,
                    attempts=attempt,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    next_action="operator_review",
                    trace=trace,
                )

        raise RuntimeError("Unexpected retry executor exit")


# ---------------------------------------------------------
# 5. EVENT DEDUPLICATION
# ---------------------------------------------------------

class EventDeduplicator:
    """
    Tracks event IDs already handled by a consumer.

    A repeated event ID is rejected before the handler
    can perform another side effect.
    """

    def __init__(self):
        self.processed_event_ids: set[str] = set()

    def is_duplicate(self, event_id: str) -> bool:
        return event_id in self.processed_event_ids

    def mark_processed(self, event_id: str) -> bool:

        if not event_id:
            raise ValueError("event_id is required")

        if self.is_duplicate(event_id):
            return False

        self.processed_event_ids.add(event_id)

        return True


# ---------------------------------------------------------
# 6. IDEMPOTENT PAYMENT PROCESSOR
# ---------------------------------------------------------

class IdempotentPaymentProcessor:
    """
    Demonstrates protection against repeated payment
    operations for the same business order.
    """

    def __init__(self):
        self.processed_payment_keys: dict[str, dict] = {}
        self.side_effect_count = 0

    def process(
        self,
        order_id: str,
        amount: float,
        idempotency_key: str,
    ) -> dict:

        if not order_id:
            raise ValueError("order_id is required")

        if amount <= 0:
            raise ValueError("amount must be positive")

        if not idempotency_key:
            raise ValueError("idempotency_key is required")

        if idempotency_key in self.processed_payment_keys:

            cached = self.processed_payment_keys[
                idempotency_key
            ]

            if (
                cached["order_id"] != order_id
                or cached["amount"] != amount
            ):
                raise ValueError(
                    "Idempotency key reused with different payment data"
                )

            return {
                **cached,
                "replayed": True,
                "next_action": "return_cached_result",
            }

        self.side_effect_count += 1

        response = {
            "order_id": order_id,
            "amount": amount,
            "payment_id": f"PAY-{order_id}",
            "status": "completed",
        }

        self.processed_payment_keys[idempotency_key] = response

        return {
            **response,
            "replayed": False,
            "next_action": "continue_workflow",
        }


# ---------------------------------------------------------
# 7. FAILURE FIXTURES
# ---------------------------------------------------------

class FailureFixture:
    """Produces controlled failures for testing and demos."""

    def __init__(self, failures: list[str]):
        self.failures = list(failures)
        self.calls = 0

    def execute(self):

        self.calls += 1

        if self.failures:

            failure = self.failures.pop(0)

            if failure == "timeout":
                raise DependencyTimeout(
                    "Dependency operation timed out"
                )

            if failure == "transient":
                raise TransientDependencyError(
                    "Temporary dependency failure"
                )

            if failure == "permanent":
                raise PermanentDependencyError(
                    "Permanent dependency rejection"
                )

            if failure == "malformed":
                raise MalformedResponseError(
                    "Dependency response was malformed"
                )

        return {
            "status": "success",
            "calls": self.calls,
        }


# ---------------------------------------------------------
# 8. TASK 3 DEMONSTRATION
# ---------------------------------------------------------

def run_task3_demo():

    # Scenario 1: Timeout followed by transient failure,
    # followed by success.
    recovery_fixture = FailureFixture([
        "timeout",
        "transient",
    ])

    recovery = RetryExecutor().execute(
        recovery_fixture.execute
    )

    # Scenario 2: Duplicate event delivery.
    deduplicator = EventDeduplicator()

    first_delivery = deduplicator.mark_processed("EVT-1001")
    replay_delivery = deduplicator.mark_processed("EVT-1001")

    # Scenario 3: Duplicate payment operation.
    processor = IdempotentPaymentProcessor()

    first_payment = processor.process(
        order_id="ORD-3001",
        amount=3500,
        idempotency_key="payment:ORD-3001",
    )

    replay_payment = processor.process(
        order_id="ORD-3001",
        amount=3500,
        idempotency_key="payment:ORD-3001",
    )

    # Scenario 4: Permanent failure.
    permanent_fixture = FailureFixture(["permanent"])

    permanent_result = RetryExecutor().execute(
        permanent_fixture.execute
    )

    # Scenario 5: Malformed response.
    malformed_fixture = FailureFixture(["malformed"])

    malformed_result = RetryExecutor().execute(
        malformed_fixture.execute
    )

    # Scenario 6: Retry exhaustion.
    exhaustion_fixture = FailureFixture([
        "timeout",
        "timeout",
        "timeout",
    ])

    exhaustion_result = RetryExecutor().execute(
        exhaustion_fixture.execute
    )

    return {
        "recovery": {
            "success": recovery.success,
            "attempts": recovery.attempts,
            "result": recovery.result,
            "next_action": recovery.next_action,
            "trace": recovery.trace,
        },
        "event_replay": {
            "first_delivery_accepted": first_delivery,
            "duplicate_delivery_accepted": replay_delivery,
            "next_action": "ignore_duplicate_event",
        },
        "payment_replay": {
            "first_payment": first_payment,
            "replay_payment": replay_payment,
            "payment_side_effect_count": processor.side_effect_count,
        },
        "permanent_failure": {
            "success": permanent_result.success,
            "error_type": permanent_result.error_type,
            "next_action": permanent_result.next_action,
            "attempts": permanent_result.attempts,
        },
        "malformed_response": {
            "success": malformed_result.success,
            "error_type": malformed_result.error_type,
            "next_action": malformed_result.next_action,
            "attempts": malformed_result.attempts,
        },
        "retry_exhaustion": {
            "success": exhaustion_result.success,
            "attempts": exhaustion_result.attempts,
            "next_action": exhaustion_result.next_action,
            "trace": exhaustion_result.trace,
        },
    }


if __name__ == "__main__":

    import json
    from pathlib import Path

    print("=" * 60)
    print("TASK 3 - FAILURE, RETRY AND REPLAY SAFETY")
    print("=" * 60)

    result = run_task3_demo()

    Path("outputs").mkdir(exist_ok=True)
    Path("traces").mkdir(exist_ok=True)

    with open(
        "outputs/task3_failure_recovery.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(result, file, indent=4)

    with open(
        "traces/task3_recovery_trace.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump({
            "recovery": result["recovery"],
            "retry_exhaustion": result["retry_exhaustion"],
        }, file, indent=4)

    print(json.dumps(result, indent=4))

    print("\nEvidence saved:")
    print("outputs/task3_failure_recovery.json")
    print("traces/task3_recovery_trace.json")
