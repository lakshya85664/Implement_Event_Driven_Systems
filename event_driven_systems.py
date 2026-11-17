
"""
Topic 2 - Task 1
Event-Driven Systems: Workflow Contract and State Model

Defines:
- Event payload schemas
- Event envelope
- Workflow run and task models
- Legal workflow state transitions
- Event recording and duplicate event identification
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# 1. WORKFLOW STATES
# ---------------------------------------------------------

class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# ---------------------------------------------------------
# 2. EVENT PAYLOAD SCHEMAS
# ---------------------------------------------------------

class OrderValidatedPayload(BaseModel):
    """Payload published when an order passes validation."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    items: list[str] = Field(min_length=1)


class PaymentCompletedPayload(BaseModel):
    """Payload published when payment processing succeeds."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    status: str = Field(pattern="^completed$")
    currency: str = Field(default="INR", min_length=3, max_length=3)


# ---------------------------------------------------------
# 3. EVENT ENVELOPE
# ---------------------------------------------------------

@dataclass
class EventEnvelope:
    """
    Standard event structure shared by producers and consumers.
    """

    event_type: str
    run_id: str
    business_key: str
    payload: dict[str, Any]

    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "business_key": self.business_key,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
            "payload": self.payload,
        }


# ---------------------------------------------------------
# 4. TASK MODEL
# ---------------------------------------------------------

@dataclass
class WorkflowTask:
    task_id: str
    name: str
    owner: str
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    result: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# 5. WORKFLOW RUN MODEL
# ---------------------------------------------------------

@dataclass
class WorkflowRun:
    run_id: str
    business_key: str
    state: WorkflowState = WorkflowState.CREATED

    attempts: int = 0

    context: dict[str, Any] = field(default_factory=dict)
    tasks: dict[str, WorkflowTask] = field(default_factory=dict)

    events: list[dict[str, Any]] = field(default_factory=list)
    processed_event_ids: set[str] = field(default_factory=set)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def record(self, event: str, **details: Any) -> None:
        """Record a structured workflow event."""

        self.events.append({
            "run_id": self.run_id,
            "event": event,
            "state": self.state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        })

    def has_processed_event(self, event_id: str) -> bool:
        """Check whether an event has already been processed."""

        return event_id in self.processed_event_ids

    def mark_event_processed(self, event_id: str) -> bool:
        """
        Mark an event as processed.

        Returns False when the event ID has already been recorded.
        """

        if self.has_processed_event(event_id):
            return False

        self.processed_event_ids.add(event_id)
        return True


# ---------------------------------------------------------
# 6. LEGAL STATE TRANSITIONS
# ---------------------------------------------------------

LEGAL_TRANSITIONS = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,

    (WorkflowState.RUNNING, "complete"): WorkflowState.COMPLETED,

    (WorkflowState.RUNNING, "pause"): WorkflowState.WAITING,

    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,

    (WorkflowState.RUNNING, "fail"): WorkflowState.NEEDS_REVIEW,

    (WorkflowState.NEEDS_REVIEW, "recover"): WorkflowState.RUNNING,

    (WorkflowState.NEEDS_REVIEW, "abort"): WorkflowState.FAILED,
}


def transition(run: WorkflowRun, event: str) -> WorkflowRun:
    """
    Apply a legal workflow state transition.

    Raises ValueError for an unsupported transition.
    """

    next_state = LEGAL_TRANSITIONS.get((run.state, event))

    if next_state is None:
        raise ValueError(
            f"Illegal transition: {run.state.value} + {event}"
        )

    previous_state = run.state

    run.state = next_state

    run.record(
        event="workflow.transition",
        trigger=event,
        previous_state=previous_state.value,
        new_state=next_state.value,
    )

    return run


# ---------------------------------------------------------
# 7. EVENT CREATION HELPERS
# ---------------------------------------------------------

def create_order_validated_event(
    run_id: str,
    payload: OrderValidatedPayload,
) -> EventEnvelope:

    return EventEnvelope(
        event_type="order.validated",
        run_id=run_id,
        business_key=payload.order_id,
        payload=payload.model_dump(),
    )


def create_payment_completed_event(
    run_id: str,
    payload: PaymentCompletedPayload,
) -> EventEnvelope:

    return EventEnvelope(
        event_type="payment.completed",
        run_id=run_id,
        business_key=payload.order_id,
        payload=payload.model_dump(),
    )


# ---------------------------------------------------------
# 8. TOPIC FIXTURE
# ---------------------------------------------------------

def run_topic_fixture() -> dict[str, Any]:
    """Demonstrate the event-driven workflow contract."""

    run = WorkflowRun(
        run_id="RUN-EVENT-1001",
        business_key="ORD-1001",
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

    transition(run, "start")

    order_payload = OrderValidatedPayload(
        order_id="ORD-1001",
        customer_id="CUST-1001",
        amount=2500.0,
        currency="INR",
        items=["Laptop Bag", "Mouse"],
    )

    order_event = create_order_validated_event(
        run.run_id,
        order_payload,
    )

    run.record(
        "event.created",
        event_id=order_event.event_id,
        event_type=order_event.event_type,
    )

    transition(run, "complete")

    return {
        "run_id": run.run_id,
        "business_key": run.business_key,
        "state": run.state.value,
        "order_event": order_event.to_dict(),
        "tasks": {
            task_id: {
                "name": task.name,
                "owner": task.owner,
                "dependencies": task.dependencies,
                "status": task.status,
            }
            for task_id, task in run.tasks.items()
        },
        "events": run.events,
        "processed_event_ids": list(run.processed_event_ids),
    }


if __name__ == "__main__":

    import json

    print("=" * 60)
    print("TOPIC 2 - TASK 1: EVENT-DRIVEN WORKFLOW CONTRACT")
    print("=" * 60)

    result = run_topic_fixture()

    print(json.dumps(result, indent=4))

    print("\nTask 1 contract demonstration completed.")
