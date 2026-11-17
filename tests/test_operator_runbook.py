
import json

import runbook


def test_required_evidence_list_contains_six_items():
    assert len(runbook.REQUIRED_EVIDENCE) == 6


def test_evidence_inspection_returns_all_required_items():
    result = runbook.inspect_evidence()

    assert set(result) == set(runbook.REQUIRED_EVIDENCE)


def test_evidence_entries_have_expected_fields():
    result = runbook.inspect_evidence()

    for item in result.values():
        assert "path" in item
        assert "exists" in item
        assert "readable" in item
        assert "size_bytes" in item


def test_evidence_report_has_summary():
    report = runbook.build_evidence_report()

    assert "evidence_summary" in report
    assert report["evidence_summary"]["total_required"] == 6


def test_evidence_report_is_json_serializable():
    report = runbook.build_evidence_report()

    serialized = json.dumps(report)
    assert json.loads(serialized)["assessment"] == (
        "Implement Event-Driven Systems"
    )


def test_operator_runbook_contains_failure_and_replay_guidance():
    content = runbook.generate_operator_runbook()

    assert "Failure handling" in content
    assert "Replay safety" in content
    assert "idempotency" in content.lower()


def test_report_generation_creates_both_files():
    generated = runbook.generate_reports()

    runbook_path = runbook.ROOT / generated["runbook"]
    evidence_path = runbook.ROOT / generated["evidence_report"]

    assert runbook_path.is_file()
    assert evidence_path.is_file()

    report = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert "evidence_summary" in report
