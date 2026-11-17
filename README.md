# Implement Event-Driven Systems

## Project overview
This project implements an event-driven order-fulfillment workflow. An order producer publishes `order.validated`; the payment consumer processes payment and publishes `payment.completed`; the shipping consumer reacts by creating a shipment.

## Objectives
- Define event envelopes and typed payloads.
- Model workflow runs, tasks, states, and transitions.
- Implement producers, consumers, and an event bus.
- Demonstrate duplicate-delivery protection, retry, and replay safety.
- Add integration adapters, structured traces, metrics, and secret redaction.
- Generate an operator runbook and evidence report.

## Task implementation
1. **Workflow contract and state model:** workflow states, order/payment payloads, event envelopes, tasks, runs, and legal transitions.
2. **Event-driven implementation:** in-memory event bus, order producer, payment consumer, shipping consumer, and order workflow.
3. **Failure, retry, and replay safety:** failure classification, bounded exponential-backoff retry decisions, event deduplication, and idempotent payment processing.
4. **Integration and observability:** payment gateway protocol and fake adapter, structured lifecycle traces, metrics, response validation, and sensitive-value redaction.
5. **Operator runbook and evidence:** operational investigation and replay guidance, plus a JSON report checking required evidence files.

## Project structure
```text
Implement_Event_Driven_Systems/
├── event_driven_systems.py
├── orchestrator.py
├── reliability.py
├── adapters.py
├── metrics.py
├── observability.py
├── runbook.py
├── requirements.txt
├── .gitignore
├── tests/
│   ├── test_workflow_contract.py
│   ├── test_orchestration.py
│   ├── test_failure_recovery.py
│   ├── test_adapters.py
│   └── test_operator_runbook.py
├── outputs/
├── traces/
└── reports/
    ├── OPERATOR_RUNBOOK.md
    └── evidence_report.json
```

## Environment
- Windows
- Python 3.13.9
- pytest 9.2.0
- Virtual environment: `.venv`

Activate and install:
```cmd
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run demonstrations
```cmd
python event_driven_systems.py
python orchestrator.py
python reliability.py
python adapters.py
python runbook.py
```

## Run tests
```cmd
python -m pytest tests\test_workflow_contract.py -v
python -m pytest tests\test_orchestration.py -v
python -m pytest tests\test_failure_recovery.py -v
python -m pytest tests\test_adapters.py -v
python -m pytest tests\test_operator_runbook.py -v
python -m pytest -v
```

## Verification results
| Task | Tests passed |
|---|---:|
| Workflow contract and state model | 12 |
| Event-driven implementation | 9 |
| Failure, retry, and replay safety | 14 |
| Integration and observability | 8 |
| Operator runbook and evidence report | 7 |
| **Total** | **50/50** |

Final observed result: **50 passed in 0.40s**.

The evidence report recorded 6 required files, 6 available, 0 missing or unreadable, and `complete: true`.

## Evidence
- `outputs/` contains task demonstration outputs.
- `traces/` contains recovery and observability traces.
- `reports/OPERATOR_RUNBOOK.md` documents investigation and replay procedures.
- `reports/evidence_report.json` records required evidence availability.

## Reflection
Building this event-driven order-fulfillment system helped me understand how independent components communicate through events rather than relying on one tightly coupled sequence of direct calls. Defining event envelopes, payload schemas, workflow states, and task dependencies first made the design easier to reason about. I learned why events need stable identifiers, run identifiers, business keys, timestamps, and schema versions: these fields support correlation, validation, and investigation.

The producer-consumer implementation demonstrated how an order can move through validation, payment, and shipping as consumers react to published events. I also learned that successful event delivery is not enough for reliability. A message can arrive more than once, a dependency can time out, and a response can be malformed. Deduplication and idempotency help prevent repeated processing and duplicate payment side effects. Retry policies must distinguish transient failures from permanent errors instead of retrying every failure indiscriminately.

The integration and observability work showed the value of adapter boundaries, structured traces, metrics, and secret redaction. These features make system behavior easier to inspect without exposing sensitive values. The operator runbook and evidence report connected implementation to operational practice by documenting investigation steps, replay precautions, and evidence locations.

The assessment passed 50 tests across five tasks. The evidence report also confirmed that all six required evidence artifacts were present and readable. A key limitation is that this is an assessment implementation: the event bus, deduplication, and idempotency state are in memory, and the payment gateway is a fake adapter. A production version would need durable messaging, persistent idempotency storage, stronger operational controls, and production-grade monitoring.
