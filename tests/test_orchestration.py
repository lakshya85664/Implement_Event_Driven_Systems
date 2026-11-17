
import pytest

from orchestrator import (
    EventBus,
    OrderProducer,
    OrderWorkflow,
)
from event_driven_systems import WorkflowRun


def valid_order():
    return {
        "order_id": "ORD-2001",
        "customer_id": "CUST-2001",
        "amount": 4500.0,
        "currency": "INR",
        "items": ["Keyboard", "Mouse"],
    }


def test_event_bus_publishes_and_dispatches():

    bus = EventBus()

    received = []

    bus.subscribe(
        "test.event",
        lambda event: received.append(event.event_type),
    )

    from event_driven_systems import EventEnvelope

    event = EventEnvelope(
        event_type="test.event",
        run_id="RUN-1",
        business_key="ORD-1",
        payload={"value": 10},
    )

    bus.publish(event)
    bus.dispatch()

    assert received == ["test.event"]
    assert len(bus.published_events) == 1
    assert bus.delivery_log[0]["status"] == "delivered"


def test_event_bus_rejects_invalid_limit():

    with pytest.raises(ValueError):
        EventBus(max_events=0)


def test_event_bus_enforces_publish_limit():

    from event_driven_systems import EventEnvelope

    bus = EventBus(max_events=1)

    event1 = EventEnvelope(
        "event.one", "RUN-1", "ORD-1", {}
    )

    event2 = EventEnvelope(
        "event.two", "RUN-1", "ORD-1", {}
    )

    bus.publish(event1)

    with pytest.raises(RuntimeError, match="Maximum event limit"):
        bus.publish(event2)


def test_order_producer_publishes_validated_event():

    bus = EventBus()

    run = WorkflowRun("RUN-1", "ORD-1")

    producer = OrderProducer(bus)

    event = producer.submit(run, valid_order())

    assert event.event_type == "order.validated"
    assert event.payload["order_id"] == "ORD-2001"
    assert len(bus.published_events) == 1


def test_order_validation_failure_publishes_nothing():

    workflow = OrderWorkflow()

    invalid_order = valid_order()
    invalid_order["amount"] = -1

    result = workflow.execute(invalid_order)

    assert result["success"] is False
    assert result["events"] == []


def test_complete_event_driven_order_workflow():

    workflow = OrderWorkflow()

    result = workflow.execute(valid_order())

    assert result["success"] is True
    assert result["state"] == "completed"

    assert result["output"]["payment"]["status"] == "completed"

    assert (
        result["output"]["shipping"]["status"]
        == "shipment_created"
    )


def test_event_order_is_correct():

    workflow = OrderWorkflow()

    result = workflow.execute(valid_order())

    event_types = [
        event["event_type"]
        for event in result["events"]
    ]

    assert event_types == [
        "order.validated",
        "payment.completed",
    ]


def test_shipping_occurs_after_payment_event():

    workflow = OrderWorkflow()

    result = workflow.execute(valid_order())

    trace_events = [
        event["event"]
        for event in result["workflow_trace"]
    ]

    payment_index = trace_events.index("payment.completed")
    shipping_index = trace_events.index("shipment.created")

    assert shipping_index > payment_index


def test_all_workflow_tasks_complete():

    workflow = OrderWorkflow()

    result = workflow.execute(valid_order())

    statuses = [
        task["status"]
        for task in result["tasks"].values()
    ]

    assert all(status == "completed" for status in statuses)
