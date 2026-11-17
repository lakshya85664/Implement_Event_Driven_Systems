
"""
Topic 2 - Task 2
Event-Driven Systems Implementation

Implements:
- In-memory event bus
- Event producer
- Payment event consumer
- Shipping event consumer
- Deterministic order fulfillment workflow
- Event dispatch limit
- Validation before side effects
"""

from collections import deque
from typing import Callable, Any
from pathlib import Path
import json

from event_driven_systems import (
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
    OrderValidatedPayload,
    PaymentCompletedPayload,
    create_order_validated_event,
    create_payment_completed_event,
    transition,
)


class EventBus:
    """A small synchronous event bus with queued delivery."""

    def __init__(self, max_events: int = 20):
        if max_events < 1:
            raise ValueError("max_events must be at least 1")

        self.max_events = max_events
        self.queue = deque()
        self.subscribers: dict[str, list[Callable]] = {}
        self.published_events = []
        self.delivery_log = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if not event_type:
            raise ValueError("event_type is required")

        self.subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event) -> None:
        """Add an event to the delivery queue."""

        if len(self.published_events) >= self.max_events:
            raise RuntimeError("Maximum event limit reached")

        self.queue.append(event)
        self.published_events.append(event.to_dict())

    def dispatch(self) -> None:
        """Deliver queued events to their registered consumers."""

        dispatched = 0

        while self.queue:
            if dispatched >= self.max_events:
                raise RuntimeError("Maximum dispatch limit reached")

            event = self.queue.popleft()
            handlers = self.subscribers.get(event.event_type, [])

            self.delivery_log.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "consumer_count": len(handlers),
                "status": "delivering",
            })

            for handler in handlers:
                handler(event)

            self.delivery_log[-1]["status"] = "delivered"
            dispatched += 1


class OrderProducer:
    """Validates an order and publishes order.validated."""

    def __init__(self, bus: EventBus):
        self.bus = bus

    def submit(self, run: WorkflowRun, order_data: dict[str, Any]):
        payload = OrderValidatedPayload(**order_data)

        event = create_order_validated_event(
            run_id=run.run_id,
            payload=payload,
        )

        run.context["order"] = payload.model_dump()
        run.record(
            "order.validated",
            event_id=event.event_id,
            order_id=payload.order_id,
        )

        self.bus.publish(event)

        return event


class PaymentConsumer:
    """Consumes validated orders and publishes completed payments."""

    def __init__(self, bus: EventBus, run: WorkflowRun):
        self.bus = bus
        self.run = run
        self.processed_orders = set()

        bus.subscribe("order.validated", self.handle)

    def handle(self, event):
        payload = OrderValidatedPayload(**event.payload)

        if payload.order_id in self.processed_orders:
            return

        self.processed_orders.add(payload.order_id)

        payment_id = f"PAY-{payload.order_id}"

        payment_payload = PaymentCompletedPayload(
            order_id=payload.order_id,
            payment_id=payment_id,
            amount=payload.amount,
            status="completed",
            currency=payload.currency,
        )

        payment_event = create_payment_completed_event(
            run_id=self.run.run_id,
            payload=payment_payload,
        )

        self.run.context["payment"] = payment_payload.model_dump()

        self.run.record(
            "payment.completed",
            event_id=payment_event.event_id,
            payment_id=payment_id,
        )

        self.bus.publish(payment_event)


class ShippingConsumer:
    """Consumes payment.completed and creates a shipment."""

    def __init__(self, bus: EventBus, run: WorkflowRun):
        self.bus = bus
        self.run = run
        self.processed_payments = set()

        bus.subscribe("payment.completed", self.handle)

    def handle(self, event):
        payload = PaymentCompletedPayload(**event.payload)

        if payload.payment_id in self.processed_payments:
            return

        self.processed_payments.add(payload.payment_id)

        shipment_id = f"SHIP-{payload.order_id}"

        self.run.context["shipping"] = {
            "status": "shipment_created",
            "shipment_id": shipment_id,
            "order_id": payload.order_id,
        }

        self.run.record(
            "shipment.created",
            shipment_id=shipment_id,
            order_id=payload.order_id,
        )


class OrderWorkflow:
    """Coordinates event producers and consumers through the event bus."""

    def __init__(self, max_events: int = 20):
        self.bus = EventBus(max_events=max_events)

    def execute(self, order_data: dict[str, Any]) -> dict[str, Any]:

        order_id = order_data.get("order_id", "INVALID")

        run = WorkflowRun(
            run_id=f"RUN-{order_id}",
            business_key=order_id,
        )

        run.tasks = {
            "validate": WorkflowTask(
                task_id="validate",
                name="Validate Order",
                owner="order_service",
            ),
            "payment": WorkflowTask(
                task_id="payment",
                name="Process Payment",
                owner="payment_service",
                dependencies=["validate"],
            ),
            "shipping": WorkflowTask(
                task_id="shipping",
                name="Create Shipment",
                owner="shipping_service",
                dependencies=["payment"],
            ),
        }

        try:
            transition(run, "start")

            producer = OrderProducer(self.bus)

            PaymentConsumer(self.bus, run)
            ShippingConsumer(self.bus, run)

            producer.submit(run, order_data)

            run.tasks["validate"].status = "completed"

            self.bus.dispatch()

            if "payment" not in run.context:
                raise RuntimeError("Payment event was not completed")

            run.tasks["payment"].status = "completed"
            run.tasks["payment"].result = run.context["payment"]

            if "shipping" not in run.context:
                raise RuntimeError("Shipping event was not completed")

            run.tasks["shipping"].status = "completed"
            run.tasks["shipping"].result = run.context["shipping"]

            transition(run, "complete")

            result = {
                "run_id": run.run_id,
                "order_id": order_id,
                "state": run.state.value,
                "success": True,
                "output": {
                    "order": run.context["order"],
                    "payment": run.context["payment"],
                    "shipping": run.context["shipping"],
                },
                "events": self.bus.published_events,
                "delivery_log": self.bus.delivery_log,
                "workflow_trace": run.events,
                "tasks": {
                    task_id: {
                        "name": task.name,
                        "owner": task.owner,
                        "dependencies": task.dependencies,
                        "status": task.status,
                    }
                    for task_id, task in run.tasks.items()
                },
                "error": None,
            }

        except Exception as exc:

            if run.state == WorkflowState.RUNNING:
                transition(run, "fail")

            result = {
                "run_id": run.run_id,
                "order_id": order_id,
                "state": run.state.value,
                "success": False,
                "output": run.context,
                "events": self.bus.published_events,
                "delivery_log": self.bus.delivery_log,
                "workflow_trace": run.events,
                "tasks": {},
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

        return result


def run_demo():
    order = {
        "order_id": "ORD-2001",
        "customer_id": "CUST-2001",
        "amount": 4500.0,
        "currency": "INR",
        "items": ["Keyboard", "Mouse"],
    }

    workflow = OrderWorkflow()
    result = workflow.execute(order)

    Path("outputs").mkdir(exist_ok=True)

    with open(
        "outputs/task2_event_driven_workflow.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(result, file, indent=4)

    return result


if __name__ == "__main__":

    print("=" * 60)
    print("TASK 2 - EVENT-DRIVEN ORDER FULFILLMENT")
    print("=" * 60)

    result = run_demo()

    print(json.dumps(result, indent=4))

    print("\nEvidence saved: outputs/task2_event_driven_workflow.json")
