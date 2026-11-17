
import pytest

from reliability import (
    RetryPolicy,
    RetryExecutor,
    FailureFixture,
    DependencyTimeout,
    PermanentDependencyError,
    MalformedResponseError,
    EventDeduplicator,
    IdempotentPaymentProcessor,
)


def test_timeout_then_success():

    fixture = FailureFixture(["timeout"])

    result = RetryExecutor().execute(fixture.execute)

    assert result.success is True
    assert result.attempts == 2
    assert result.result["status"] == "success"


def test_transient_failure_then_success():

    fixture = FailureFixture(["transient"])

    result = RetryExecutor().execute(fixture.execute)

    assert result.success is True
    assert result.attempts == 2


def test_retry_exhaustion():

    fixture = FailureFixture([
        "timeout",
        "timeout",
        "timeout",
    ])

    result = RetryExecutor().execute(fixture.execute)

    assert result.success is False
    assert result.attempts == 3
    assert result.next_action == "operator_review"


def test_permanent_failure_is_not_retried():

    fixture = FailureFixture(["permanent"])

    result = RetryExecutor().execute(fixture.execute)

    assert result.success is False
    assert result.attempts == 1
    assert result.error_type == "PermanentDependencyError"
    assert result.next_action == "quarantine_and_review"


def test_malformed_response_is_quarantined():

    fixture = FailureFixture(["malformed"])

    result = RetryExecutor().execute(fixture.execute)

    assert result.success is False
    assert result.attempts == 1
    assert result.error_type == "MalformedResponseError"
    assert result.next_action == "quarantine_and_review"


def test_event_duplicate_is_rejected():

    deduplicator = EventDeduplicator()

    assert deduplicator.mark_processed("EVT-1") is True
    assert deduplicator.mark_processed("EVT-1") is False


def test_different_event_ids_are_accepted():

    deduplicator = EventDeduplicator()

    assert deduplicator.mark_processed("EVT-1") is True
    assert deduplicator.mark_processed("EVT-2") is True


def test_duplicate_payment_does_not_repeat_side_effect():

    processor = IdempotentPaymentProcessor()

    first = processor.process(
        "ORD-1",
        2500,
        "payment:ORD-1",
    )

    replay = processor.process(
        "ORD-1",
        2500,
        "payment:ORD-1",
    )

    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert replay["next_action"] == "return_cached_result"
    assert processor.side_effect_count == 1


def test_idempotency_key_cannot_be_reused_for_different_data():

    processor = IdempotentPaymentProcessor()

    processor.process(
        "ORD-1",
        2500,
        "payment:ORD-1",
    )

    with pytest.raises(ValueError, match="different payment data"):
        processor.process(
            "ORD-2",
            3000,
            "payment:ORD-1",
        )


def test_retry_backoff_is_bounded():

    policy = RetryPolicy(
        max_attempts=5,
        initial_backoff=1,
        max_backoff=4,
    )

    assert policy.backoff_for(1) == 1
    assert policy.backoff_for(2) == 2
    assert policy.backoff_for(3) == 4
    assert policy.backoff_for(4) == 4


def test_invalid_retry_policy_rejected():

    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


def test_empty_event_id_rejected():

    deduplicator = EventDeduplicator()

    with pytest.raises(ValueError, match="event_id"):
        deduplicator.mark_processed("")


def test_invalid_payment_amount_rejected():

    processor = IdempotentPaymentProcessor()

    with pytest.raises(ValueError, match="positive"):
        processor.process(
            "ORD-1",
            -100,
            "payment:ORD-1",
        )


def test_retry_backoff_rejects_invalid_attempt():

    policy = RetryPolicy()

    with pytest.raises(ValueError):
        policy.backoff_for(0)
