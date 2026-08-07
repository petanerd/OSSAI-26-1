import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from verifiable_ai_workflow.release_monitoring import (
    HumanDecision,
    build_monitoring_record,
    combine_weekly_results,
)


def test_nightly_record_has_only_operational_fields(
    tmp_path: Path,
    project_root: Path,
) -> None:
    summary = {
        "record_count": 3,
        "score_averages": {"task_success": 1.0},
        "provider_error_count": 0,
        "actual_models": ["google/gemma-4-31b-it"],
        "provenance": {"git_sha": "a" * 40, "prompt_sha256": "b" * 64},
    }
    calls = [
        {
            "latency_ms": value,
            "input_tokens": 10,
            "output_tokens": 5,
            "actual_cost_usd": 0,
        }
        for value in (100, 200, 300)
    ]
    summary_path, calls_path = tmp_path / "summary.json", tmp_path / "calls.jsonl"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    calls_path.write_text(
        "".join(json.dumps(item) + "\n" for item in calls), encoding="utf-8"
    )

    record = build_monitoring_record(
        profile="nightly",
        summary_path=summary_path,
        calls_path=calls_path,
        config_path=project_root / "configs/week-06.yaml",
        timestamp=datetime(2026, 8, 7, tzinfo=UTC),
    )

    assert record.automated_status == "pass"
    assert record.p95_latency_ms == 300
    assert record.input_tokens == 30


def test_weekly_combines_validation_and_challenge() -> None:
    validation = {
        "record_count": 8,
        "score_averages": {"task_success": 1.0},
        "provenance": {"git_sha": "a" * 40},
    }
    robustness = {"record_count": 5, "git_sha": "a" * 40}
    combined = combine_weekly_results(
        validation,
        robustness,
        [{"status": "passed"}] * 5,
    )
    assert combined["record_count"] == 13
    assert combined["score_averages"]["task_success"] == 1


def test_ship_requires_pass_and_completed_human_audit() -> None:
    with pytest.raises(ValidationError, match="SHIP"):
        HumanDecision(
            timestamp=datetime.now(UTC),
            decision="SHIP",
            reviewer="reviewer-1",
            reason="검토 완료",
            automated_status="pass",
            human_audit_complete=False,
        )
