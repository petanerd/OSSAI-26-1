import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace import TracerProvider

from scripts import run_agent_live
from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    load_agent_upstream_context,
)
from verifiable_ai_workflow.release_monitoring import build_monitoring_record


def _upstream_args(monkeypatch, project_root: Path) -> list[str]:
    fixture = project_root / "data/recorded/week-05-upstream.json"
    upstream = load_agent_upstream_context(fixture).model_copy(
        update={"source_evidence_kind": "live_quality"}
    )
    monkeypatch.setattr(run_agent_live, "_load_upstream_context", lambda *args: upstream)
    return [
        "--upstream-summary",
        str(fixture),
        "--upstream-responses",
        str(fixture),
        "--prompt-selection-summary",
        str(fixture),
        "--selected-prompt",
        str(fixture),
    ]


def _argv(
    tmp_path: Path,
    *,
    profile: str | None,
    max_requests: int = 11,
    wall_seconds: int = 1800,
    sample_id: str | None = None,
    evaluation: Path | None = None,
    upstream_args: list[str] | None = None,
) -> list[str]:
    args = ["run_agent_live.py", "--live", "--phoenix"]
    if profile is not None:
        args.extend(("--profile", profile))
    if sample_id is not None:
        args.extend(("--sample-id", sample_id))
    if evaluation is not None:
        args.extend(("--upstream-evaluation", str(evaluation)))
    source_args = upstream_args or [
        "--upstream-summary",
        "summary.json",
        "--upstream-responses",
        "responses.jsonl",
        "--prompt-selection-summary",
        "selection.json",
        "--selected-prompt",
        "prompt.md",
    ]
    args.extend(
        [
            *source_args,
            "--max-requests",
            str(max_requests),
            "--max-input-tokens",
            str(max_requests * 20_000),
            "--max-output-tokens",
            str(max_requests * 500),
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            str(wall_seconds),
            "--catalog-verified-on",
            "2026-08-31",
            "--pricing-verified-on",
            "2026-08-31",
            "--output",
            str(tmp_path / f"output-{profile}"),
        ]
    )
    return args


@pytest.mark.parametrize(
    ("profile", "sample_id", "max_requests", "wall_seconds", "expected_ids"),
    [
        (
            "nightly",
            run_agent_live.NIGHTLY_AGENT_ID,
            3,
            360,
            (run_agent_live.NIGHTLY_AGENT_ID,),
        ),
        ("weekly", None, 11, 1800, run_agent_live.FULL_AGENT_IDS),
    ],
)
def test_week6_profiles_emit_monitoring_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_root: Path,
    profile: str,
    sample_id: str | None,
    max_requests: int,
    wall_seconds: int,
    expected_ids: tuple[str, ...],
) -> None:
    recorded = RecordedAgentProvider(
        project_root / "data/recorded/week-05-agent-turns.jsonl"
    )

    class Provider:
        evidence_kind = "live_quality"
        model = "nvidia_nim/google/gemma-4-31b-it"
        expected_actual_model = "google/gemma-4-31b-it"
        structured_output = "json_schema"
        last_call = None

        def __init__(self, on_response, on_call_finished) -> None:
            self.on_response = on_response
            self.on_call_finished = on_call_finished
            self.request_count = 0
            self.budget = SimpleNamespace(
                summary=lambda: {
                    "request_count": self.request_count,
                    "attempt_count": self.request_count,
                }
            )

        def generate(self, case_id, messages, *, response_schema):
            raw = recorded.generate(case_id, messages, response_schema=response_schema)
            self.request_count += 1
            call = {
                "sample_id": case_id,
                "requested_model": self.model,
                "expected_actual_model": self.expected_actual_model,
                "actual_model": self.expected_actual_model,
                "actual_model_matches_expected": True,
                "provider_status": "success",
                "raw_response": {"content": raw},
                "response_received_at": "2026-08-31T00:00:00Z",
                "latency_ms": 1.0,
                "input_tokens": 1,
                "output_tokens": 1,
                "actual_cost_usd": 0.0,
                "error_type": None,
            }
            self.last_call = call
            self.on_response(
                {**call, "provider_status": "provider_response_received"}
            )
            self.on_call_finished(dict(call))
            return raw

    upstream_args = _upstream_args(monkeypatch, project_root)
    monkeypatch.setattr(
        run_agent_live,
        "build_course_provider",
        lambda *args, **kwargs: Provider(
            kwargs["on_response"], kwargs["on_call_finished"]
        ),
    )
    monkeypatch.setattr(run_agent_live, "load_project_env", lambda *args: None)
    monkeypatch.setattr(run_agent_live, "_git_sha", lambda: "a" * 40)
    monkeypatch.setattr(run_agent_live, "_require_recent_verification", lambda *args: None)
    monkeypatch.setattr(
        run_agent_live,
        "build_phoenix_tracer",
        lambda: TracerProvider().get_tracer("week-06-profile-test"),
    )
    monkeypatch.setattr(run_agent_live, "record_with_deepeval", lambda *args: None)
    monkeypatch.setattr(
        run_agent_live,
        "verify_phoenix_traces",
        lambda runs, **kwargs: {run.sample_id: run.phoenix_trace_id for run in runs},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(
            tmp_path,
            profile=profile,
            sample_id=sample_id,
            max_requests=max_requests,
            wall_seconds=wall_seconds,
            upstream_args=upstream_args,
        ),
    )

    assert run_agent_live.main() == 0
    output = tmp_path / f"output-{profile}"
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["profile"] == profile
    assert summary["run_id"].startswith(f"week06-{profile}-")
    assert summary["status"] == "pass"
    assert summary["observed_status"] == "complete"
    assert summary["target_sample_ids"] == list(expected_ids)
    assert summary["passed"] == summary["total"] == len(expected_ids)
    assert summary["budget"]["request_count"] == max_requests
    assert summary["component_statuses"] == {
        "agent_safety": "pass",
        "monitoring": "pass",
    }
    assert "upstream_answer_quality_status" not in summary
    assert "upstream-evaluation.json" not in summary["source_input_sha256"]
    assert summary["release_config_sha256"] == run_agent_live._sha256(
        project_root / "configs/week-06.yaml"
    )
    assert len((output / "calls.jsonl").read_text().splitlines()) == max_requests

    if profile == "nightly":
        record = build_monitoring_record(
            profile="nightly",
            summary_path=output / "summary.json",
            calls_path=output / "calls.jsonl",
            config_path=project_root / "configs/week-06.yaml",
        )
        assert record.automated_status == "pass"


@pytest.mark.parametrize(
    ("profile", "sample_id", "evaluation", "message"),
    [
        ("week5", None, None, "--upstream-evaluation"),
        ("week5", run_agent_live.NIGHTLY_AGENT_ID, Path("evaluation.json"), "nightly"),
        ("nightly", None, None, "W5-06-idempotent-retry"),
        (
            "nightly",
            run_agent_live.NIGHTLY_AGENT_ID,
            Path("evaluation.json"),
            "받지 않습니다",
        ),
        ("weekly", run_agent_live.NIGHTLY_AGENT_ID, None, "nightly"),
        ("weekly", None, Path("evaluation.json"), "받지 않습니다"),
    ],
)
def test_profile_specific_arguments_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile: str,
    sample_id: str | None,
    evaluation: Path | None,
    message: str,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(
            tmp_path,
            profile=profile,
            sample_id=sample_id,
            evaluation=evaluation,
        ),
    )

    with pytest.raises(SystemExit, match=message):
        run_agent_live.main()


def test_profile_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, profile=None))

    with pytest.raises(SystemExit):
        run_agent_live.main()
