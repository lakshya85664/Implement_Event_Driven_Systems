
"""
Topic 2 - Task 4
Injectable payment integration boundary.
"""

from typing import Protocol
from time import perf_counter

from observability import WorkflowObserver
from metrics import WorkflowMetrics


class PaymentGateway(Protocol):

    def charge(
        self,
        order_id: str,
        amount: float,
        idempotency_key: str,
    ) -> dict:
        ...


class FakePaymentGateway:
    """Local fake payment service for assessment testing."""

    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0
        self.side_effect_count = 0
        self.cache = {}

    def charge(
        self,
        order_id: str,
        amount: float,
        idempotency_key: str,
    ) -> dict:

        self.calls += 1

        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        if idempotency_key in self.cache:
            return self.cache[idempotency_key]

        if self.failure == "timeout":
            from reliability import DependencyTimeout
            raise DependencyTimeout("Payment gateway timeout")

        if self.failure == "transient":
            from reliability import TransientDependencyError
            raise TransientDependencyError(
                "Temporary gateway failure"
            )

        if self.failure == "permanent":
            from reliability import PermanentDependencyError
            raise PermanentDependencyError(
                "Payment rejected"
            )

        if self.failure == "malformed":
            return {
                "order_id": order_id,
                "status": "unknown",
            }

        self.side_effect_count += 1

        response = {
            "order_id": order_id,
            "amount": amount,
            "payment_id": f"PAY-{order_id}",
            "status": "completed",
        }

        self.cache[idempotency_key] = response

        return response


class PaymentAdapter:

    def __init__(
        self,
        gateway: PaymentGateway,
        observer: WorkflowObserver,
        metrics: WorkflowMetrics,
    ):
        self.gateway = gateway
        self.observer = observer
        self.metrics = metrics

    def process_payment(
        self,
        run_id: str,
        order_id: str,
        amount: float,
    ) -> dict:

        idempotency_key = f"payment:{order_id}"

        self.observer.emit(
            "payment.started",
            run_id,
            "running",
            {
                "order_id": order_id,
                "amount": amount,
            },
        )

        self.metrics.increment("payment.started")
        self.metrics.record_event("payment.started")

        started = perf_counter()

        try:
            response = self.gateway.charge(
                order_id,
                amount,
                idempotency_key,
            )

            if (
                not isinstance(response, dict)
                or response.get("status") != "completed"
                or not response.get("payment_id")
            ):
                from reliability import MalformedResponseError
                raise MalformedResponseError(
                    "Invalid payment gateway response"
                )

            latency_ms = (perf_counter() - started) * 1000

            self.metrics.increment("payment.succeeded")
            self.metrics.record_latency("payment", latency_ms)
            self.metrics.record_event("payment.completed")

            self.observer.emit(
                "payment.completed",
                run_id,
                "completed",
                {
                    "order_id": order_id,
                    "payment_id": response["payment_id"],
                    "latency_ms": round(latency_ms, 3),
                },
            )

            return response

        except Exception as exc:

            latency_ms = (perf_counter() - started) * 1000

            self.metrics.increment("payment.failed")
            self.metrics.record_latency("payment", latency_ms)
            self.metrics.record_event("payment.failed")

            self.observer.emit(
                "payment.failed",
                run_id,
                "needs_review",
                {
                    "order_id": order_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": round(latency_ms, 3),
                },
            )

            raise


def run_task4_demo():

    observer = WorkflowObserver()
    metrics = WorkflowMetrics()

    gateway = FakePaymentGateway()

    adapter = PaymentAdapter(
        gateway=gateway,
        observer=observer,
        metrics=metrics,
    )

    response = adapter.process_payment(
        run_id="RUN-OBS-4001",
        order_id="ORD-4001",
        amount=4500,
    )

    return {
        "payment_response": response,
        "status": observer.get_status("RUN-OBS-4001"),
        "trace": observer.get_trace("RUN-OBS-4001"),
        "metrics": metrics.report(),
    }


if __name__ == "__main__":

    import json
    from pathlib import Path

    print("=" * 60)
    print("TASK 4 - INTEGRATION AND OBSERVABILITY")
    print("=" * 60)

    result = run_task4_demo()

    Path("outputs").mkdir(exist_ok=True)

    with open(
        "outputs/task4_observability.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(result, file, indent=4)

    print(json.dumps(result, indent=4))
    print("\nEvidence saved: outputs/task4_observability.json")
