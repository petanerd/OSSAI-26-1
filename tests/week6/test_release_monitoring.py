import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from scripts import combine_weekly_results as combine_script
from verifiable_ai_workflow.release_monitoring import (
    AGENT_MUST_PASS,
    HumanAudit,
    HumanDecision,
    MonitoringRecord,
    _require_source_summary,
    build_monitoring_record,
    combine_weekly_results,
)

GIT_SHA = "a" * 40
PROMPT_SHA = "b" * 64
SELECTED_PROMPT_SHA = "c" * 64
AGENT_PROMPT_SHA = "d" * 64
ROBUSTNESS_RESPONSES_SHA = "2" * 64
UPSTREAM_SOURCE_SUMMARY_SHA = "3" * 64
UPSTREAM_OUTPUT_SHA = "4" * 64
MODEL = "google/gemma-4-31b-it"
REQUESTED_MODEL = "nvidia_nim/google/gemma-4-31b-it"
OPTIMIZER_MODEL = "gemini/gemini-3.5-flash-lite"
VARIANT_IDS = ["original", "rotate-2", "jpeg-60", "crop-left", "occlude-answer"]
AGENT_IDS = [
    "W5-01-direct",
    "W5-02-calculator",
    "W5-03-lookup",
    "W5-04-ticket",
    "W5-05-pii-denial",
    "W5-06-idempotent-retry",
]
HIGH_RISK_IDS = AGENT_IDS[3:]
PHOENIX_TRACE_IDS = {
    sample_id: f"{index:032x}" for index, sample_id in enumerate(AGENT_IDS, start=1)
}
NIGHTLY_IDS = ["W5-06-idempotent-retry"]
WEEKLY_IDS = [
    *(f"884:{variant_id}" for variant_id in VARIANT_IDS),
    *AGENT_IDS,
]
SELECTION_SOURCE = {
    "dataset_sha256": "1" * 64,
    "source_split": "val",
    "source_revision": "1" * 40,
    "source_license": "GPL-3.0",
}


def _provider(role: str, requested: str, expected: str) -> dict:
    return {
        "role": role,
        "requested_model": requested,
        "expected_actual_model": expected,
        "actual_models": [expected],
        "provider_error_count": 0,
        "model_drift_count": 0,
    }


def _source(**changes) -> dict:
    source = {
        "profile": "weekly",
        "evidence_kind": "live_quality",
        "status": "pass",
        "observed_status": "complete",
        "git_sha": GIT_SHA,
        "requested_model": REQUESTED_MODEL,
        "expected_actual_model": MODEL,
        "actual_models": [MODEL],
        "provider_error_count": 0,
        "model_drift_count": 0,
    }
    source.update(changes)
    return source


def _weekly_inputs() -> tuple[dict, list[dict], dict, list[dict], dict]:
    robustness = _source(
        record_count=5,
        target_count=5,
        target_variant_ids=VARIANT_IDS,
        completed_variant_ids=VARIANT_IDS,
        sample_id="884",
        family_id="opencqa-val-884",
        source_split="val",
        source_revision="1" * 40,
        source_license="GPL-3.0",
        prompt_sha256=SELECTED_PROMPT_SHA,
        artifact_sha256={"responses.jsonl": ROBUSTNESS_RESPONSES_SHA},
    )
    robustness_scores = [
        {"variant_id": variant_id, "status": "passed"} for variant_id in VARIANT_IDS
    ]
    agent = _source(
        record_count=6,
        target_count=6,
        target_sample_ids=AGENT_IDS,
        completed_sample_ids=AGENT_IDS,
        high_risk_sample_ids=HIGH_RISK_IDS,
        prompt_sha256=AGENT_PROMPT_SHA,
        metric_passed={name: 6 for name in AGENT_MUST_PASS},
        metric_record_count=6,
        phoenix_trace_ids=copy.deepcopy(PHOENIX_TRACE_IDS),
        upstream_sample_id="884",
        upstream_family_id="opencqa-val-884",
        upstream_selected_prompt_sha256=SELECTED_PROMPT_SHA,
        upstream_selection_summary_sha256="f" * 64,
        upstream_source_summary_sha256=UPSTREAM_SOURCE_SUMMARY_SHA,
        upstream_responses_sha256=ROBUSTNESS_RESPONSES_SHA,
        upstream_output_sha256=UPSTREAM_OUTPUT_SHA,
    )
    agent_scores = [
        {
            "sample_id": sample_id,
            "status": "passed",
            "evidence_kind": "live_quality",
            "scores": {name: 1.0 for name in AGENT_MUST_PASS},
        }
        for sample_id in AGENT_IDS
    ]
    selection = {
        "status": "pass",
        "observed_status": "complete",
        "evidence_kind": "live_quality",
        "selected": "candidate",
        "git_sha": "e" * 40,
        "selected_prompt_sha256": SELECTED_PROMPT_SHA,
        "selection_summary_sha256": "f" * 64,
        "test_used_for_generation_or_selection": False,
        "development_count": 18,
        "validation_count": 6,
        "test_count": 6,
        "selection_reason": "validation_improved",
        **copy.deepcopy(SELECTION_SOURCE),
        "target_provider": _provider("target", REQUESTED_MODEL, MODEL),
        "optimizer_provider": _provider("optimizer", OPTIMIZER_MODEL, "gemini-3.5-flash-lite"),
        "provider_error_count": 0,
        "model_drift_count": 0,
    }
    return robustness, robustness_scores, agent, agent_scores, selection


def _combine(inputs: tuple[dict, list[dict], dict, list[dict], dict]) -> dict:
    robustness, robustness_scores, agent, agent_scores, selection = inputs
    return combine_weekly_results(
        robustness,
        robustness_scores,
        agent,
        agent_scores,
        expected_agent_ids=AGENT_IDS,
        expected_high_risk_ids=HIGH_RISK_IDS,
        selected_prompt_sha256=SELECTED_PROMPT_SHA,
        prompt_selection=selection,
        evaluator_git_sha=GIT_SHA,
    )


def test_weekly_is_an_and_gate_over_all_agent_metrics() -> None:
    assert len(AGENT_MUST_PASS) == 7
    assert "workflow_lineage" in AGENT_MUST_PASS
    combined = _combine(_weekly_inputs())
    assert combined["status"] == "pass"
    assert combined["observed_status"] == "complete"
    assert combined["record_count"] == combined["target_count"] == 11
    assert combined["component_statuses"] == {
        "robustness": "pass",
        "agent": "pass",
    }
    assert combined["phoenix_trace_ids"] == PHOENIX_TRACE_IDS

    inputs = _weekly_inputs()
    inputs[3][0]["status"] = "failed"
    inputs[3][0]["scores"]["authorization_safety"] = 0
    inputs[2]["metric_passed"]["authorization_safety"] = 5
    failed = _combine(inputs)
    assert failed["status"] == "fail"
    assert failed["score_averages"]["task_success"] == 0
    assert failed["component_statuses"]["agent"] == "fail"


def test_weekly_rejects_agent_summary_that_hides_a_failed_metric() -> None:
    inputs = _weekly_inputs()
    inputs[2]["metric_passed"].pop("tool_budget")
    with pytest.raises(ValueError, match="must-pass"):
        _combine(inputs)


@pytest.mark.parametrize(
    "trace_ids",
    [
        {},
        {**PHOENIX_TRACE_IDS, AGENT_IDS[0]: "A" * 32},
        {
            **PHOENIX_TRACE_IDS,
            AGENT_IDS[1]: PHOENIX_TRACE_IDS[AGENT_IDS[0]],
        },
    ],
)
def test_weekly_requires_complete_unique_phoenix_trace_ids(trace_ids: dict) -> None:
    inputs = _weekly_inputs()
    inputs[2]["phoenix_trace_ids"] = trace_ids

    with pytest.raises(ValueError, match="Phoenix"):
        _combine(inputs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("upstream_sample_id", "wrong-sample"),
        ("upstream_family_id", "wrong-family"),
        ("upstream_selected_prompt_sha256", "0" * 64),
        ("upstream_selection_summary_sha256", "0" * 64),
        ("upstream_responses_sha256", "0" * 64),
    ],
)
def test_weekly_rejects_broken_week4_to_week5_lineage(field: str, value: str) -> None:
    inputs = _weekly_inputs()
    inputs[2][field] = value
    with pytest.raises(ValueError, match="workflow 계보"):
        _combine(inputs)


def test_weekly_requires_source_and_original_output_hashes() -> None:
    for field in ("upstream_source_summary_sha256", "upstream_output_sha256"):
        inputs = _weekly_inputs()
        inputs[2][field] = None
        with pytest.raises(ValueError, match="upstream"):
            _combine(inputs)


def test_robustness_inconclusive_makes_overall_inconclusive() -> None:
    inputs = _weekly_inputs()
    inputs[1][0]["status"] = "inconclusive"
    combined = _combine(inputs)
    assert combined["status"] == "inconclusive"
    assert combined["observed_status"] == "complete"
    assert combined["score_averages"]["task_success"] is None
    assert combined["component_statuses"]["robustness"] == "inconclusive"


def test_robustness_score_failure_is_visible_in_component_status() -> None:
    inputs = _weekly_inputs()
    inputs[1][0]["status"] = "failed"

    combined = _combine(inputs)

    assert combined["status"] == "fail"
    assert combined["component_statuses"] == {
        "robustness": "fail",
        "agent": "pass",
    }


def test_not_run_sources_are_preserved_as_not_run() -> None:
    inputs = _weekly_inputs()
    robustness, robustness_scores, agent, agent_scores, _ = inputs
    robustness.update(
        status="inconclusive",
        observed_status="not_run",
        record_count=0,
        completed_variant_ids=[],
        actual_models=[],
    )
    robustness_scores.clear()
    agent.update(
        status="inconclusive",
        observed_status="not_run",
        record_count=0,
        completed_sample_ids=[],
        actual_models=[],
        metric_passed={name: 0 for name in AGENT_MUST_PASS},
        metric_record_count=0,
        phoenix_trace_ids={},
    )
    agent_scores.clear()
    combined = _combine(inputs)
    assert combined["status"] == "inconclusive"
    assert combined["observed_status"] == "not_run"
    assert combined["record_count"] == 0


@pytest.mark.parametrize(
    "observed", ["complete", "partial", "blocked", "inconclusive", "not_run"]
)
def test_source_observed_status_vocabulary(observed: str) -> None:
    result = _require_source_summary(_source(observed_status=observed), profile="weekly")
    assert result[1] == observed


def test_old_fail_observed_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="observed_status"):
        _require_source_summary(_source(observed_status="fail"), profile="weekly")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "fail"),
        ("evidence_kind", "test_only"),
        ("test_used_for_generation_or_selection", True),
        ("selected", None),
        ("development_count", 17),
        ("target_provider", {}),
        ("optimizer_provider", _provider("optimizer", OPTIMIZER_MODEL, "")),
        ("provider_error_count", 1),
        ("dataset_sha256", "invalid"),
        ("source_split", "test"),
        ("git_sha", "invalid"),
        ("selected_prompt_sha256", "0" * 64),
    ],
)
def test_prompt_selection_requires_bound_live_metadata(field: str, value: object) -> None:
    inputs = _weekly_inputs()
    inputs[4][field] = value
    with pytest.raises(ValueError):
        _combine(inputs)


def test_wrong_evaluator_commit_is_rejected() -> None:
    robustness, robustness_scores, agent, agent_scores, selection = _weekly_inputs()
    with pytest.raises(ValueError, match="평가 코드의 Git SHA"):
        combine_weekly_results(
            robustness,
            robustness_scores,
            agent,
            agent_scores,
            expected_agent_ids=AGENT_IDS,
            expected_high_risk_ids=HIGH_RISK_IDS,
            selected_prompt_sha256=SELECTED_PROMPT_SHA,
            prompt_selection=selection,
            evaluator_git_sha="0" * 40,
        )


def _write_nightly_artifacts(tmp_path: Path, release_config: Path) -> tuple[Path, Path, dict]:
    calls = [
        {
            "sample_id": NIGHTLY_IDS[0],
            "requested_model": REQUESTED_MODEL,
            "expected_actual_model": MODEL,
            "actual_model": MODEL,
            "actual_model_matches_expected": True,
            "provider_status": "provider_response_received",
            "raw_response": {"id": NIGHTLY_IDS[0]},
            "response_received_at": "2026-08-08T00:00:00Z",
            "latency_ms": latency,
            "input_tokens": 10,
            "output_tokens": 5,
            "actual_cost_usd": 0.0,
            "error_type": None,
        }
        for latency in (100, 200, 300)
    ]
    calls_path = tmp_path / "calls.jsonl"
    calls_path.write_text("".join(json.dumps(row) + "\n" for row in calls), encoding="utf-8")
    summary = {
        "profile": "nightly",
        "status": "pass",
        "observed_status": "complete",
        "evidence_kind": "live_quality",
        "record_count": 1,
        "target_count": 1,
        "sample_ids": NIGHTLY_IDS,
        "high_risk_sample_ids": NIGHTLY_IDS,
        "score_averages": {"task_success": 1.0},
        "provider_error_count": 0,
        "model_drift_count": 0,
        "requested_model": REQUESTED_MODEL,
        "expected_actual_model": MODEL,
        "actual_models": [MODEL],
        "release_config_sha256": hashlib.sha256(release_config.read_bytes()).hexdigest(),
        "artifact_sha256": {"calls.jsonl": hashlib.sha256(calls_path.read_bytes()).hexdigest()},
        "provenance": {"git_sha": GIT_SHA, "prompt_sha256": PROMPT_SHA},
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary_path, calls_path, summary


def test_monitoring_record_requires_bound_complete_calls(
    tmp_path: Path, project_root: Path
) -> None:
    release_config = project_root / "configs/week-06.yaml"
    summary_path, calls_path, summary = _write_nightly_artifacts(tmp_path, release_config)
    record = build_monitoring_record(
        profile="nightly",
        summary_path=summary_path,
        calls_path=calls_path,
        config_path=release_config,
        timestamp=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert record.automated_status == "pass"
    assert record.p95_latency_ms == 300

    calls_path.write_text(calls_path.read_text().replace('"raw_response"', '"removed"'))
    summary["artifact_sha256"]["calls.jsonl"] = hashlib.sha256(calls_path.read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    assert build_monitoring_record(
        profile="nightly",
        summary_path=summary_path,
        calls_path=calls_path,
        config_path=release_config,
    ).automated_status == "inconclusive"


@pytest.mark.parametrize("model_mismatch", [False, True], ids=["success", "model-mismatch"])
def test_monitoring_usage_includes_received_error_responses(
    tmp_path: Path, project_root: Path, model_mismatch: bool,
) -> None:
    config = project_root / "configs/week-06.yaml"
    summary_path, calls_path, summary = _write_nightly_artifacts(tmp_path, config)
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    for index, call in enumerate(calls, start=1):
        call["actual_cost_usd"] = index * 0.001
    if model_mismatch:
        calls[-1].update(
            error_type="ActualModelMismatch",
            provider_status="provider_error",
            actual_model="different-model",
            actual_model_matches_expected=False,
        )
        summary.update(
            status="inconclusive", observed_status="partial", model_drift_count=1,
            actual_models=[MODEL, "different-model"],
        )
    calls_path.write_text("".join(json.dumps(call) + "\n" for call in calls), encoding="utf-8")
    summary["artifact_sha256"]["calls.jsonl"] = hashlib.sha256(calls_path.read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    record = build_monitoring_record(
        profile="nightly", summary_path=summary_path, calls_path=calls_path, config_path=config,
    )

    assert record.input_tokens == 30
    assert record.output_tokens == 15
    assert record.cost_usd == pytest.approx(0.006)
    assert record.p95_latency_ms == (200 if model_mismatch else 300)
    assert record.automated_status == ("inconclusive" if model_mismatch else "pass")
    assert record.error_count == int(model_mismatch)


def test_weekly_history_preserves_evaluated_component_statuses(
    tmp_path: Path,
    project_root: Path,
) -> None:
    inputs = _weekly_inputs()
    inputs[1][0]["status"] = "failed"
    summary = _combine(inputs)
    calls = [
        {
            "sample_id": sample_id,
            "requested_model": REQUESTED_MODEL,
            "expected_actual_model": MODEL,
            "actual_model": MODEL,
            "actual_model_matches_expected": True,
            "provider_status": "success",
            "raw_response": {"id": sample_id},
            "response_received_at": "2026-08-08T00:00:00Z",
            "latency_ms": 100,
            "input_tokens": 10,
            "output_tokens": 5,
            "actual_cost_usd": 0.0,
            "error_type": None,
        }
        for sample_id in WEEKLY_IDS
    ]
    calls_path = tmp_path / "calls.jsonl"
    calls_path.write_text(
        "".join(json.dumps(row) + "\n" for row in calls), encoding="utf-8"
    )
    config = project_root / "configs/week-06.yaml"
    summary.update(
        release_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        artifact_sha256={"calls.jsonl": hashlib.sha256(calls_path.read_bytes()).hexdigest()},
    )
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    record = build_monitoring_record(
        profile="weekly",
        summary_path=summary_path,
        calls_path=calls_path,
        config_path=config,
    )

    assert record.automated_status == "fail"
    assert record.component_statuses == {
        "robustness": "fail",
        "agent": "pass",
    }


def test_weekly_monitoring_pass_requires_every_component_pass() -> None:
    with pytest.raises(ValidationError, match="전체 통과 계약"):
        MonitoringRecord(
            timestamp=datetime(2026, 8, 8, tzinfo=UTC),
            profile="weekly",
            git_sha=GIT_SHA,
            requested_model=REQUESTED_MODEL,
            expected_actual_model=MODEL,
            actual_model=MODEL,
            model_identity_matches=True,
            prompt_sha256=PROMPT_SHA,
            selected_prompt_sha256=SELECTED_PROMPT_SHA,
            agent_prompt_sha256=AGENT_PROMPT_SHA,
            sample_ids=WEEKLY_IDS,
            high_risk_sample_ids=HIGH_RISK_IDS,
            component_statuses={
                "robustness": "fail",
                "agent": "pass",
            },
            component_record_counts={"robustness": 5, "agent": 6},
            record_count=11,
            task_success=1,
            p95_latency_ms=100,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0,
            error_count=0,
            automated_status="pass",
        )


def test_ship_requires_high_risk_and_independent_random_audit() -> None:
    monitored_at = datetime(2026, 8, 8, 10, tzinfo=UTC)
    common = {
        "timestamp": monitored_at + timedelta(hours=2),
        "reviewer": "reviewer-1",
        "reason": "검토 완료",
        "monitoring_record_sha256": "c" * 64,
        "monitoring_timestamp": monitored_at,
        "profile": "weekly",
        "git_sha": GIT_SHA,
        "requested_model": REQUESTED_MODEL,
        "actual_model": MODEL,
        "prompt_sha256": PROMPT_SHA,
        "selected_prompt_sha256": SELECTED_PROMPT_SHA,
        "agent_prompt_sha256": AGENT_PROMPT_SHA,
        "sample_ids": WEEKLY_IDS,
        "high_risk_sample_ids": HIGH_RISK_IDS,
        "automated_status": "pass",
    }
    audit = HumanAudit(
        completed_at=monitored_at + timedelta(hours=1),
        reviewed_sample_ids=[*HIGH_RISK_IDS, AGENT_IDS[0]],
        random_sample_ids=[AGENT_IDS[0]],
        notes="고위험 전수와 무작위 한 건 확인",
    )
    assert HumanDecision(**common, decision="SHIP", human_audit=audit).decision == "SHIP"

    false_pass = audit.model_copy(update={"false_pass_sample_ids": [HIGH_RISK_IDS[0]]})
    with pytest.raises(ValidationError, match="false pass"):
        HumanDecision(**common, decision="SHIP", human_audit=false_pass)


def test_combine_script_binds_agent_to_actual_week4_files(
    monkeypatch, tmp_path: Path
) -> None:
    robustness_dir = tmp_path / "robustness"
    selection_dir = tmp_path / "selection"
    agent_dir = tmp_path / "agent"
    for path in (robustness_dir, selection_dir, agent_dir):
        path.mkdir()
    output = {
        "answer": "47%",
        "evidence": [{"evidence_id": "e1", "quote": "47%", "page_number": 1}],
        "confidence": 0.9,
        "abstained": False,
        "abstention_reason": None,
        "tool_requests": [],
    }
    responses_path = robustness_dir / "responses.jsonl"
    responses_path.write_text(
        json.dumps({"variant_id": "original", "output": output}) + "\n",
        encoding="utf-8",
    )
    robustness_summary_path = robustness_dir / "summary.json"
    robustness_summary_path.write_text("{}", encoding="utf-8")
    selection_summary_path = selection_dir / "summary.json"
    selection_summary_path.write_text("{}", encoding="utf-8")
    expected_output_hash = hashlib.sha256(
        json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    selection_hash = hashlib.sha256(selection_summary_path.read_bytes()).hexdigest()
    agent = {
        "status": "inconclusive",
        "upstream_source_summary_sha256": hashlib.sha256(
            robustness_summary_path.read_bytes()
        ).hexdigest(),
        "upstream_responses_sha256": hashlib.sha256(responses_path.read_bytes()).hexdigest(),
        "upstream_output_sha256": expected_output_hash,
        "upstream_selection_summary_sha256": selection_hash,
    }
    args = SimpleNamespace(
        robustness_summary=robustness_summary_path,
        robustness_calls=robustness_dir / "calls.jsonl",
        robustness_scores=robustness_dir / "evaluation.json",
        agent_summary=agent_dir / "summary.json",
        agent_calls=agent_dir / "calls.jsonl",
        agent_scores=agent_dir / "scores.jsonl",
        prompt_selection_summary=selection_summary_path,
        selected_prompt=selection_dir / "selected-prompt.md",
    )
    robustness = {"status": "inconclusive"}
    selection = {"selection_summary_sha256": selection_hash}
    monkeypatch.setattr(combine_script, "require_bound_artifact", lambda *args, **kwargs: None)

    combine_script._validate_source_artifacts(args, robustness, agent, selection)
    assert combine_script._original_output_sha256(responses_path) == expected_output_hash

    for field in (
        "upstream_source_summary_sha256",
        "upstream_responses_sha256",
        "upstream_output_sha256",
        "upstream_selection_summary_sha256",
    ):
        broken = {**agent, field: "0" * 64}
        with pytest.raises(ValueError, match="실제 파일"):
            combine_script._validate_source_artifacts(args, robustness, broken, selection)


def test_combine_script_requires_real_agent_summary(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    args = SimpleNamespace(
        agent_summary=agent_dir / "summary.json",
        agent_calls=agent_dir / "calls.jsonl",
        agent_scores=agent_dir / "scores.jsonl",
    )

    with pytest.raises(ValueError, match="agent summary가 필요"):
        combine_script._load_agent_summary(args)

    agent_dir.mkdir()
    args.agent_calls.write_text("partial\n", encoding="utf-8")
    with pytest.raises(ValueError, match="일부 실행 파일"):
        combine_script._load_agent_summary(args)
