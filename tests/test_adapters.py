
import pytest

from adapters import (
    FakePaymentGateway,
    PaymentAdapter,
)

from observability import (
    WorkflowObserver,
    redact_secrets,
)

from metrics import WorkflowMetrics

from reliability import (
    DependencyTimeout,
    MalformedResponseError,
    PermanentDependencyError,
)


def create_adapter(tmp_path, failure=None):

    observer = WorkflowObserver(
        str(tmp_path / "events.jsonl")
    )

    metrics = WorkflowMetrics()

    gateway = FakePaymentGateway(failure=failure)

    adapter = PaymentAdapter(
        gateway,
        observer,
        metrics,
    )

    return adapter, observer, metrics, gateway


def test_payment_adapter_success(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(tmp_path)

    result = adapter.process_payment(
        "RUN-1",
        "ORD-1",
        2500,
    )

    assert result["status"] == "completed"
    assert result["payment_id"] == "PAY-ORD-1"
    assert gateway.side_effect_count == 1

    assert observer.get_status("RUN-1")["state"] == "completed"


def test_structured_trace_generated(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(tmp_path)

    adapter.process_payment("RUN-2", "ORD-2", 1500)

    trace = observer.get_trace("RUN-2")

    assert len(trace) == 2
    assert trace[0]["event_type"] == "payment.started"
    assert trace[1]["event_type"] == "payment.completed"


def test_dependency_failure_is_observable(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(
        tmp_path,
        failure="timeout",
    )

    with pytest.raises(DependencyTimeout):
        adapter.process_payment("RUN-3", "ORD-3", 1500)

    assert observer.get_status("RUN-3")["state"] == "needs_review"
    assert metrics.counters["payment.failed"] == 1


def test_secrets_are_redacted():

    data = {
        "username": "user1",
        "api_key": "secret-value",
        "nested": {
            "password": "hidden",
        },
    }

    result = redact_secrets(data)

    assert result["api_key"] == "***REDACTED***"
    assert result["nested"]["password"] == "***REDACTED***"
    assert result["username"] == "user1"


def test_metrics_report(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(tmp_path)

    adapter.process_payment("RUN-4", "ORD-4", 2000)

    report = metrics.report()

    assert report["counters"]["payment.succeeded"] == 1
    assert report["latency"]["measurements"] == 1
    assert report["event_count"] == 2


def test_malformed_gateway_response_rejected(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(
        tmp_path,
        failure="malformed",
    )

    with pytest.raises(MalformedResponseError):
        adapter.process_payment("RUN-5", "ORD-5", 1000)

    assert metrics.counters["payment.failed"] == 1


def test_permanent_gateway_failure_observed(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(
        tmp_path,
        failure="permanent",
    )

    with pytest.raises(PermanentDependencyError):
        adapter.process_payment("RUN-6", "ORD-6", 1000)

    assert observer.get_status("RUN-6")["state"] == "needs_review"


def test_invalid_amount_rejected(tmp_path):

    adapter, observer, metrics, gateway = create_adapter(tmp_path)

    with pytest.raises(ValueError, match="positive"):
        adapter.process_payment("RUN-7", "ORD-7", -100)

    assert gateway.side_effect_count == 0
