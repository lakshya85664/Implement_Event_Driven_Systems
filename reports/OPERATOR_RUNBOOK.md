# Operator Runbook — Event-Driven Order Fulfillment

## 1. System overview

This project demonstrates an event-driven order fulfillment workflow.
An order producer publishes an `order.validated` event. A payment
consumer processes the order and publishes `payment.completed`.
A shipping consumer reacts to the payment event and creates a shipment.

## 2. Normal workflow

1. Validate the incoming order.
2. Publish the `order.validated` event.
3. Dispatch the event to subscribed consumers.
4. Process payment using an idempotency key.
5. Publish `payment.completed` after successful payment.
6. Create the shipment.
7. Inspect the workflow output and trace records.

## 3. Failure handling

| Failure | Expected operator action |
|---|---|
| Transient dependency error | Allow the configured retry policy to retry |
| Dependency timeout | Check dependency availability and retry outcome |
| Permanent dependency error | Inspect the failure; do not retry blindly |
| Malformed response | Quarantine or investigate the invalid response |
| Retry exhaustion | Review the run and decide whether a controlled replay is safe |
| Duplicate event | Confirm it was rejected by event deduplication |
| Duplicate payment request | Confirm the idempotency key prevents a second side effect |

## 4. Investigation procedure

1. Identify the affected run ID and business order ID.
2. Inspect the corresponding workflow output under `outputs/`.
3. Inspect recovery traces under `traces/`.
4. Check event names, timestamps, and workflow state transitions.
5. Review counters and latency measurements in the observability output.
6. Check whether an event was duplicated, rejected, retried, or quarantined.
7. Record the operator decision before attempting a replay.

## 5. Replay safety

Never replay a payment operation without checking its idempotency key.
Confirm that the business order data matches the original request.
A repeated event ID should be rejected by the deduplication mechanism.
Investigate uncertain payment outcomes before initiating another operation.

## 6. Evidence locations

- `outputs/task1_contract_output.txt`
- `outputs/task2_event_driven_workflow.json`
- `outputs/task3_failure_recovery.json`
- `outputs/task4_observability.json`
- `traces/task3_recovery_trace.json`
- `traces/task4_events.jsonl`

The generated evidence report records which required files are present
and readable.

## 7. Operational limitations

This assessment uses an in-memory event bus and in-memory deduplication
and idempotency state. The fake payment gateway is for testing only.
The implementation does not provide durable message storage, distributed
locking, production authentication, or a persistent recovery database.
A production deployment would require durable infrastructure and
operational monitoring.

## 8. Verification commands

Run the complete test suite:

    python -m pytest -v

Run the demonstrations:

    python event_driven_systems.py
    python orchestrator.py
    python reliability.py
    python adapters.py
    python runbook.py
