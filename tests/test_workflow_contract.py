
import pytest
from pydantic import ValidationError

from event_driven_systems import (
    WorkflowRun,
    WorkflowState,
    OrderValidatedPayload,
    PaymentCompletedPayload,
    EventEnvelope,
    create_order_validated_event,
    create_payment_completed_event,
    transition,
    run_topic_fixture,
)


def test_legal_transition_created_to_running():

    run = WorkflowRun(
        run_id="RUN-1",
        business_key="ORD-1",
    )

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING


def test_illegal_transition_is_rejected():

    run = WorkflowRun(
        run_id="RUN-2",
        business_key="ORD-2",
    )

    with pytest.raises(ValueError, match="Illegal transition"):
        transition(run, "complete")


def test_running_to_waiting_and_resume():

    run = WorkflowRun("RUN-3", "ORD-3")

    transition(run, "start")
    transition(run, "pause")

    assert run.state == WorkflowState.WAITING

    transition(run, "resume")

    assert run.state == WorkflowState.RUNNING


def test_order_validated_payload():

    payload = OrderValidatedPayload(
        order_id="ORD-100",
        customer_id="CUST-100",
        amount=1500,
        items=["Keyboard"],
    )

    assert payload.order_id == "ORD-100"
    assert payload.amount == 1500


def test_invalid_order_payload_rejected():

    with pytest.raises(ValidationError):
        OrderValidatedPayload(
            order_id="",
            customer_id="CUST-100",
            amount=-100,
            items=[],
        )


def test_payment_completed_payload():

    payload = PaymentCompletedPayload(
        order_id="ORD-200",
        payment_id="PAY-200",
        amount=2500,
        status="completed",
    )

    assert payload.status == "completed"


def test_invalid_payment_status_rejected():

    with pytest.raises(ValidationError):
        PaymentCompletedPayload(
            order_id="ORD-200",
            payment_id="PAY-200",
            amount=2500,
            status="pending",
        )


def test_order_event_creation():

    payload = OrderValidatedPayload(
        order_id="ORD-300",
        customer_id="CUST-300",
        amount=3000,
        items=["Monitor"],
    )

    event = create_order_validated_event("RUN-300", payload)

    assert event.event_type == "order.validated"
    assert event.business_key == "ORD-300"
    assert event.event_id


def test_payment_event_creation():

    payload = PaymentCompletedPayload(
        order_id="ORD-400",
        payment_id="PAY-400",
        amount=4000,
        status="completed",
    )

    event = create_payment_completed_event("RUN-400", payload)

    assert event.event_type == "payment.completed"
    assert event.payload["payment_id"] == "PAY-400"


def test_event_envelope_serialization():

    event = EventEnvelope(
        event_type="order.validated",
        run_id="RUN-500",
        business_key="ORD-500",
        payload={"amount": 500},
    )

    data = event.to_dict()

    assert data["event_id"] == event.event_id
    assert data["event_type"] == "order.validated"
    assert data["payload"]["amount"] == 500


def test_duplicate_event_detection():

    run = WorkflowRun("RUN-600", "ORD-600")

    assert run.mark_event_processed("EVENT-1") is True
    assert run.mark_event_processed("EVENT-1") is False

    assert run.has_processed_event("EVENT-1")


def test_fixture_returns_valid_contract():

    result = run_topic_fixture()

    assert result["run_id"] == "RUN-EVENT-1001"
    assert result["state"] == "completed"
    assert result["order_event"]["event_type"] == "order.validated"
    assert "payment" in result["tasks"]
