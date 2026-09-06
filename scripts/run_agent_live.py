"""Week 5 agent 사례를 실제 task model과 로컬 도구 sandbox로 실행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from verifiable_ai_workflow.agent_lab import (
    build_phoenix_tracer,
    load_agent_cases,
    load_lookup_records,
    record_with_deepeval,
    run_cases,
    verify_phoenix_traces,
)
from verifiable_ai_workflow.config.secrets import load_project_env
from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.course_live import build_course_provider, summarize_call_failures
from verifiable_ai_workflow.image_robustness import VariantScore
from verifiable_ai_workflow.live_execution import LiveBudgetCaps
from verifiable_ai_workflow.schemas import StructuredAnswer
from verifiable_ai_workflow.schemas.agent import (
    AgentUpstreamContext,
    structured_answer_sha256,
)
from verifiable_ai_workflow.workflow.agent_runner import AgentExecutionError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_CASES = PROJECT_ROOT / "data/agent/week-05-cases.yaml"
AGENT_LOOKUP = PROJECT_ROOT / "data/agent/week-05-lookup.yaml"
AGENT_MANIFEST = PROJECT_ROOT / "data/agent/week-05-manifest.yaml"
OPEN_CQA_SELECTION = Path("data/opencqa/week-03-selection.yaml")
RELEASE_CONFIG = PROJECT_ROOT / "configs/week-06.yaml"
NIGHTLY_AGENT_ID = "W5-06-idempotent-retry"
FULL_AGENT_IDS = (
    "W5-01-direct",
    "W5-02-calculator",
    "W5-03-lookup",
    "W5-04-ticket",
    "W5-05-pii-denial",
    "W5-06-idempotent-retry",
)
APPROVED_PROVIDER = {
    "kind": "litellm",
    "model": "nvidia_nim/google/gemma-4-31b-it",
    "expected_actual_model": "google/gemma-4-31b-it",
    "api_base": "https://integrate.api.nvidia.com/v1",
    "api_key_env": "NVIDIA_NIM_API_KEY",
    "structured_output": "json_schema",
    "billing_basis": "developer_program_free_endpoint",
    "pricing_source_url": "https://docs.api.nvidia.com/nim/docs/product",
    "input_cost_per_token_usd": 0.0,
    "output_cost_per_token_usd": 0.0,
    "temperature": 0.0,
    "top_p": None,
    "seed": None,
    "sampling_parameters": "explicit",
    "thinking_mode": "default",
    "thinking_parameter": "thinking",
    "max_images_per_prompt": None,
}
APPROVED_REQUEST_SETTINGS = {
    "requests_per_minute": 20,
    "max_retries": 0,
    "retry_initial_seconds": 5.0,
    "request_input_token_ceiling": 20_000,
    "request_output_token_ceiling": 500,
    "request_timeout_seconds": 120.0,
}


def required_live_requests(cases) -> int:
    return sum(case.max_tool_calls + 1 for case in cases)


def _classify_agent_safety(
    *,
    observed_status: str,
    passed: int,
    total: int,
    provider_error_count: int,
    model_identity_matches: bool,
    input_changed: bool,
) -> str:
    if (
        observed_status != "complete"
        or provider_error_count
        or not model_identity_matches
        or input_changed
    ):
        return "inconclusive"
    return "pass" if passed == total else "fail"


def _combine_component_statuses(statuses: dict[str, str]) -> str:
    return (
        "inconclusive"
        if "inconclusive" in statuses.values()
        else "fail"
        if "fail" in statuses.values()
        else "pass"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_files(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _sha256(path) for name, path in paths.items()}


def _files_changed(paths: dict[str, Path], expected: dict[str, str]) -> bool:
    return any(
        not path.is_file() or _sha256(path) != expected[name]
        for name, path in paths.items()
    )


class _RunTracer:
    def __init__(self, tracer, *, run_id: str, trial_id: str) -> None:
        self._tracer = tracer
        self._attributes = {
            "course.run_id": run_id,
            "course.trial_id": trial_id,
        }

    def start_as_current_span(self, name: str, **kwargs):
        attributes = {**kwargs.pop("attributes", {}), **self._attributes}
        return self._tracer.start_as_current_span(
            name,
            attributes=attributes,
            **kwargs,
        )


def _require_approved_provider(settings) -> None:
    actual_provider = {
        field: getattr(settings.provider, field) for field in APPROVED_PROVIDER
    }
    actual_requests = {
        field: getattr(settings.limits, field) for field in APPROVED_REQUEST_SETTINGS
    }
    if actual_provider != APPROVED_PROVIDER or actual_requests != APPROVED_REQUEST_SETTINGS:
        raise SystemExit("승인된 Week 5 NVIDIA endpoint·key·model·요청 설정만 사용합니다")


def _source_manifest(
    cases,
    upstream_context: AgentUpstreamContext | None = None,
) -> dict:
    agent_manifest = yaml.safe_load(AGENT_MANIFEST.read_text(encoding="utf-8"))
    all_case_rows = yaml.safe_load(AGENT_CASES.read_text(encoding="utf-8"))["cases"]
    lookup_rows = yaml.safe_load(AGENT_LOOKUP.read_text(encoding="utf-8"))["records"]
    if (
        agent_manifest["case_count"] != len(all_case_rows)
        or agent_manifest["family_count"]
        != len({row["family_id"] for row in all_case_rows})
        or agent_manifest["lookup_record_count"] != len(lookup_rows)
    ):
        raise SystemExit("Week 5 manifest의 사례·family·조회 record 수가 입력 파일과 다릅니다")
    upstream_reference = agent_manifest["upstream_reference"]
    if any(
        case.source_sample_id != upstream_reference["sample_id"]
        or case.family_id != upstream_reference["family_id"]
        for case in cases
    ):
        raise SystemExit("Week 5 사례와 manifest의 Week 4 입력 계보가 다릅니다")
    if upstream_context is not None and any(
        actual != upstream_reference[name]
        for name, actual in {
            "sample_id": upstream_context.sample_id,
            "family_id": upstream_context.family_id,
            "source_revision": upstream_context.source_revision,
            "source_license": upstream_context.source_license,
        }.items()
    ):
        raise SystemExit("Week 5 manifest와 실제 Week 4 입력 계보가 다릅니다")
    manifest = {
        **agent_manifest,
        "agent_manifest_sha256": _sha256(AGENT_MANIFEST),
        "agent_cases_sha256": _sha256(AGENT_CASES),
        "lookup_records_sha256": _sha256(AGENT_LOOKUP),
        "selected_case_count": len(cases),
        "sample_ids": [case.sample_id for case in cases],
        "upstream_reference": upstream_reference,
    }
    if upstream_context is not None:
        manifest["upstream_reference"] = {
            **upstream_reference,
            "source_evidence_kind": upstream_context.source_evidence_kind,
            "source_status": upstream_context.source_status,
        }
        manifest["upstream_artifact_sha256"] = {
            "selected-prompt.md": upstream_context.selected_prompt_sha256,
            "prompt-selection-summary.json": upstream_context.selection_summary_sha256,
            "robustness-summary.json": upstream_context.source_summary_sha256,
            "responses.jsonl": upstream_context.responses_sha256,
            "original-output.json": upstream_context.output_sha256,
        }
    return manifest


def _project_file(path: Path, label: str, *, project_root: Path) -> Path:
    resolved = path.resolve()
    root = project_root.resolve()
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise SystemExit(f"{label}은 프로젝트 안의 실제 파일이어야 합니다")
    return resolved


def _read_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label}을 JSON으로 읽을 수 없습니다") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label}은 JSON object여야 합니다")
    return payload


def _load_upstream_answer_quality(
    evaluation: Path,
    upstream_summary: Path,
    upstream_responses: Path,
    *,
    project_root: Path | None = None,
) -> dict[str, str]:
    root = (project_root or PROJECT_ROOT).resolve()
    evaluation_path = _project_file(
        evaluation, "--upstream-evaluation", project_root=root
    )
    manifest_path = _project_file(
        evaluation_path.parent / "evaluation-manifest.json",
        "evaluation-manifest.json",
        project_root=root,
    )
    summary_path = _project_file(
        upstream_summary, "--upstream-summary", project_root=root
    )
    responses_path = _project_file(
        upstream_responses, "--upstream-responses", project_root=root
    )
    summary = _read_json(summary_path, "Week 4 이미지 견고성 summary")
    manifest = _read_json(manifest_path, "Week 4 evaluation manifest")
    expected_manifest = {
        "evaluation_sha256": _sha256(evaluation_path),
        "responses_sha256": _sha256(responses_path),
        "source_git_sha": summary.get("git_sha"),
        "schema_sha256": summary.get("schema_sha256"),
    }
    if any(
        not isinstance(expected, str) or manifest.get(name) != expected
        for name, expected in expected_manifest.items()
    ) or any(
        not isinstance(value := manifest.get(name), str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
        for name, length in {
            "source_git_sha": 40,
            "schema_sha256": 64,
            "scorer_sha256": 64,
            "metric_sha256": 64,
        }.items()
    ):
        raise SystemExit("Week 4 evaluation manifest의 품질 평가 계보가 다릅니다")
    try:
        payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("evaluation root는 list여야 합니다")
        scores = [VariantScore.model_validate(item) for item in payload]
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit("Week 4 evaluation을 VariantScore 목록으로 읽을 수 없습니다") from exc
    originals = [score for score in scores if score.variant_id == "original"]
    if len(originals) != 1:
        raise SystemExit("Week 4 evaluation에는 original 품질 점수가 정확히 한 건 필요합니다")
    original = originals[0]
    if original.grounding_status != "preserved":
        raise SystemExit("Week 4 original 품질 점수는 preserved 근거여야 합니다")
    return {
        "status": {
            "passed": "pass",
            "failed": "fail",
            "inconclusive": "inconclusive",
            "invalid_variant": "inconclusive",
        }[original.status],
        "reason": original.reason,
    }


def _load_upstream_context(
    upstream_summary: Path,
    upstream_responses: Path,
    prompt_selection_summary: Path,
    selected_prompt: Path,
    *,
    project_root: Path | None = None,
) -> AgentUpstreamContext:
    root = (project_root or PROJECT_ROOT).resolve()
    summary_path, responses_path, selection_path, prompt_path = (
        _project_file(path, label, project_root=root)
        for path, label in (
            (upstream_summary, "--upstream-summary"),
            (upstream_responses, "--upstream-responses"),
            (prompt_selection_summary, "--prompt-selection-summary"),
            (selected_prompt, "--selected-prompt"),
        )
    )
    summary = _read_json(summary_path, "Week 4 이미지 견고성 summary")
    selection_summary = _read_json(selection_path, "Week 4 지시문 선택 summary")
    source_selection = yaml.safe_load(
        (root / OPEN_CQA_SELECTION).read_text(encoding="utf-8")
    )
    if source_selection["course_splits"]["development"][0] != "884":
        raise SystemExit("Week 4 고정 개발 사례가 OpenCQA 884가 아닙니다")
    expected_source = {
        "sample_id": "884",
        "family_id": "opencqa-val-884",
        "course_split": "development",
        "source_split": source_selection["source_split"],
        "source_revision": source_selection["revision"],
        "source_license": source_selection["license"],
    }
    if any(summary.get(key) != value for key, value in expected_source.items()):
        raise SystemExit("Week 4 이미지 견고성 summary의 OpenCQA 884 계보가 다릅니다")
    if (
        summary.get("evidence_kind") != "live_quality"
        or summary.get("observed_status") != "complete"
        or summary.get("status") != "pass"
    ):
        raise SystemExit(
            "Week 4 이미지 견고성 결과는 완료되고 구조 수집을 통과한 live_quality여야 합니다"
        )
    if (
        selection_summary.get("status") != "pass"
        or selection_summary.get("observed_status") != "complete"
        or selection_summary.get("evidence_kind") != "live_quality"
        or any(
            selection_summary.get(key) != expected_source[key]
            for key in ("source_split", "source_revision", "source_license")
        )
    ):
        raise SystemExit("Week 4 지시문 선택 결과는 통과한 live_quality여야 합니다")

    responses_sha256 = _sha256(responses_path)
    if summary.get("artifact_sha256", {}).get("responses.jsonl") != responses_sha256:
        raise SystemExit("Week 4 responses.jsonl SHA-256이 summary와 다릅니다")
    prompt_sha256 = _sha256(prompt_path)
    if (
        summary.get("prompt_sha256") != prompt_sha256
        or selection_summary.get("selected_prompt_sha256") != prompt_sha256
        or selection_summary.get("artifact_sha256", {}).get("selected-prompt.md")
        != prompt_sha256
    ):
        raise SystemExit("Week 4 선택 지시문 SHA-256 계보가 다릅니다")

    try:
        rows = [
            json.loads(line)
            for line in responses_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit("Week 4 responses.jsonl을 읽을 수 없습니다") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise SystemExit("Week 4 responses.jsonl의 각 행은 JSON object여야 합니다")
    original_rows = [row for row in rows if row.get("variant_id") == "original"]
    if (
        len(original_rows) != 1
        or "parse_error" not in original_rows[0]
        or original_rows[0]["parse_error"] is not None
    ):
        raise SystemExit("Week 4 responses에 구조가 유효한 original 한 건이 필요합니다")
    try:
        output = StructuredAnswer.model_validate(original_rows[0].get("output"))
    except ValueError as exc:
        raise SystemExit("Week 4 original 답이 StructuredAnswer 형식과 다릅니다") from exc
    return AgentUpstreamContext(
        sample_id=summary["sample_id"],
        family_id=summary["family_id"],
        source_revision=summary["source_revision"],
        source_license=summary["source_license"],
        selected_prompt_sha256=prompt_sha256,
        selection_summary_sha256=_sha256(selection_path),
        source_summary_sha256=_sha256(summary_path),
        responses_sha256=responses_sha256,
        output_sha256=structured_answer_sha256(output),
        output=output,
        source_evidence_kind="live_quality",
        source_status=summary["status"],
    )


def _require_recent_verification(
    catalog_verified_on: date,
    pricing_verified_on: date | None,
    *,
    today: date | None = None,
) -> None:
    today = today or date.today()
    catalog_age = (today - catalog_verified_on).days
    if catalog_age < 0 or catalog_age > 7:
        raise ValueError("--catalog-verified-on은 오늘부터 7일 이내여야 합니다")
    if pricing_verified_on is None:
        raise ValueError("NVIDIA NIM 가격 근거 날짜가 없습니다")
    pricing_age = (today - pricing_verified_on).days
    if pricing_age < 0 or pricing_age > 7:
        raise ValueError("NVIDIA NIM 가격 근거 날짜는 오늘부터 7일 이내여야 합니다")


def _git_sha() -> str:
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise SystemExit("agent 실제 실행은 변경사항이 없는 Git commit에서만 허용합니다")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--phoenix", action="store_true")
    parser.add_argument(
        "--profile", choices=("week5", "nightly", "weekly"), required=True
    )
    parser.add_argument("--sample-id")
    parser.add_argument("--upstream-summary", type=Path, required=True)
    parser.add_argument("--upstream-responses", type=Path, required=True)
    parser.add_argument("--upstream-evaluation", type=Path)
    parser.add_argument("--prompt-selection-summary", type=Path, required=True)
    parser.add_argument("--selected-prompt", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--catalog-verified-on", type=date.fromisoformat, required=True)
    parser.add_argument("--pricing-verified-on", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.profile == "week5":
        if args.upstream_evaluation is None:
            raise SystemExit("week5 profile에는 --upstream-evaluation이 필요합니다")
        if args.sample_id is not None:
            raise SystemExit("--sample-id는 nightly profile에만 허용됩니다")
    else:
        if args.upstream_evaluation is not None:
            raise SystemExit("Week 6 profile에는 --upstream-evaluation을 받지 않습니다")
        if args.profile == "nightly" and args.sample_id != NIGHTLY_AGENT_ID:
            raise SystemExit(
                "nightly profile에는 --sample-id W5-06-idempotent-retry가 필요합니다"
            )
        if args.profile == "weekly" and args.sample_id is not None:
            raise SystemExit("--sample-id는 nightly profile에만 허용됩니다")
    if not args.live:
        raise SystemExit("실제 task model 호출에는 --live가 필요합니다")
    if not args.phoenix:
        raise SystemExit("agent 실제 실행에는 로컬 Phoenix와 --phoenix가 필요합니다")
    upstream_context = _load_upstream_context(
        args.upstream_summary,
        args.upstream_responses,
        args.prompt_selection_summary,
        args.selected_prompt,
    )
    case_path = AGENT_CASES
    prompt_path = PROJECT_ROOT / "prompts/week-05-agent.md"
    all_cases = load_agent_cases(case_path)
    if tuple(case.sample_id for case in all_cases) != FULL_AGENT_IDS:
        raise SystemExit("agent 사례 파일은 고정 여섯 사례여야 합니다")
    cases = (
        [case for case in all_cases if case.sample_id == NIGHTLY_AGENT_ID]
        if args.profile == "nightly"
        else all_cases
    )
    if args.profile == "nightly" and len(cases) != 1:
        raise SystemExit("nightly profile의 고정 사례를 찾을 수 없습니다")
    required = required_live_requests(cases)
    if args.max_requests != required:
        raise SystemExit(f"선택한 사례 실행에는 --max-requests {required}이 필요합니다")
    upstream_answer_quality = (
        _load_upstream_answer_quality(
            args.upstream_evaluation,
            args.upstream_summary,
            args.upstream_responses,
        )
        if args.profile == "week5"
        else None
    )
    settings = load_settings(PROJECT_ROOT / "configs/nvidia-nim-gemma4.yaml")
    _require_approved_provider(settings)
    _require_recent_verification(
        args.catalog_verified_on,
        args.pricing_verified_on,
    )
    caps = LiveBudgetCaps(
        max_requests=args.max_requests,
        max_attempts=args.max_requests,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_cost_usd=args.max_cost_usd,
        max_wall_seconds=args.max_wall_seconds,
    )
    approved_caps = LiveBudgetCaps(
        max_requests=required,
        max_attempts=required,
        max_input_tokens=required * 20_000,
        max_output_tokens=required * 500,
        max_cost_usd=0.01,
        max_wall_seconds=required * 120 if args.profile == "nightly" else 1_800,
    )
    if caps != approved_caps:
        raise SystemExit("agent 실제 실행은 선택 사례에 맞는 문서의 승인 cap이 필요합니다")
    git_sha = _git_sha()
    started_at = datetime.now(UTC)
    run_scope = "week05" if args.profile == "week5" else f"week06-{args.profile}"
    run_id = f"{run_scope}-{started_at:%Y%m%dT%H%M%SZ}-{git_sha[:8]}"
    trial_ids = {case.sample_id: f"{case.sample_id}-t01" for case in cases}
    source_manifest = _source_manifest(cases, upstream_context)
    source_paths = {
        "agent-manifest.yaml": AGENT_MANIFEST,
        "agent-cases.yaml": AGENT_CASES,
        "lookup-records.yaml": AGENT_LOOKUP,
        "open-cqa-selection.yaml": PROJECT_ROOT / OPEN_CQA_SELECTION,
        "upstream-summary.json": args.upstream_summary.resolve(),
        "upstream-responses.jsonl": args.upstream_responses.resolve(),
        "prompt-selection-summary.json": args.prompt_selection_summary.resolve(),
        "selected-prompt.md": args.selected_prompt.resolve(),
        "agent-prompt.md": prompt_path,
        "provider-config.yaml": PROJECT_ROOT / "configs/nvidia-nim-gemma4.yaml",
        "uv.lock": PROJECT_ROOT / "uv.lock",
        "run-agent-live.py": PROJECT_ROOT / "scripts/run_agent_live.py",
        "agent-schema.py": PROJECT_ROOT / "src/verifiable_ai_workflow/schemas/agent.py",
        "structured-answer-schema.py": (
            PROJECT_ROOT / "src/verifiable_ai_workflow/schemas/models.py"
        ),
        "agent-scorer.py": (
            PROJECT_ROOT / "src/verifiable_ai_workflow/evaluation/agent_scoring.py"
        ),
        "agent-lab.py": PROJECT_ROOT / "src/verifiable_ai_workflow/agent_lab.py",
        "agent-runner.py": (
            PROJECT_ROOT / "src/verifiable_ai_workflow/workflow/agent_runner.py"
        ),
        "tool-sandbox.py": PROJECT_ROOT / "src/verifiable_ai_workflow/tools/sandbox.py",
    }
    source_paths.update(
        {
            "upstream-evaluation.json": args.upstream_evaluation.resolve(),
            "upstream-evaluation-manifest.json": (
                args.upstream_evaluation.parent / "evaluation-manifest.json"
            ).resolve(),
        }
        if args.profile == "week5"
        else {"release-config.yaml": RELEASE_CONFIG}
    )
    source_input_sha256 = _snapshot_files(source_paths)
    tracer = build_phoenix_tracer()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    load_project_env(PROJECT_ROOT)
    calls_path = args.output / "calls.jsonl"
    receipts_path = args.output / "response-receipts.jsonl"
    partial_runs_path = args.output / "partial-runs.jsonl"
    receipts_path.touch()
    call_records: list[dict] = []
    response_receipt_count = 0
    active_trial_id: str | None = None

    def record_call(call: dict) -> None:
        call = dict(call)
        call_records.append(call)
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {**call, "run_id": run_id, "trial_id": active_trial_id},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def record_receipt(call: dict) -> None:
        nonlocal response_receipt_count
        with receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {**call, "run_id": run_id, "trial_id": active_trial_id},
                    ensure_ascii=False,
                )
                + "\n"
            )
        response_receipt_count += 1

    provider = build_course_provider(
        settings,
        caps,
        structured_output="json_schema",
        on_response=record_receipt,
        on_call_finished=record_call,
    )
    runs = []
    scores = []
    completed_cases = []
    execution_error: Exception | None = None
    prompt = prompt_path.read_text(encoding="utf-8")
    records = load_lookup_records(AGENT_LOOKUP)
    for case in cases:
        active_trial_id = trial_ids[case.sample_id]
        try:
            case_runs, case_scores = run_cases(
                [case],
                provider,
                upstream_context=upstream_context,
                prompt=prompt,
                records=records,
                tracer=_RunTracer(
                    tracer,
                    run_id=run_id,
                    trial_id=active_trial_id,
                ),
            )
        except Exception as exc:
            execution_error = exc.cause if isinstance(exc, AgentExecutionError) else exc
            if isinstance(exc, AgentExecutionError):
                partial_runs_path.write_text(
                    json.dumps(
                        {
                            **exc.partial_record,
                            "run_id": run_id,
                            "trial_id": active_trial_id,
                            "git_sha": git_sha,
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            terminal_call = getattr(provider, "last_call", None)
            if terminal_call is not None and (
                not call_records or terminal_call != call_records[-1]
            ):
                record_call(dict(terminal_call))
            break
        completed_cases.append(case)
        runs.extend(case_runs)
        scores.extend(case_scores)
    (args.output / "runs.jsonl").write_text(
        "".join(run.model_dump_json() + "\n" for run in runs), encoding="utf-8"
    )
    (args.output / "scores.jsonl").write_text(
        "".join(score.model_dump_json() + "\n" for score in scores), encoding="utf-8"
    )
    if completed_cases:
        try:
            record_with_deepeval(completed_cases, runs, scores, args.output / "deepeval")
        except Exception as exc:
            execution_error = execution_error or exc
    passed = sum(score.status == "passed" for score in scores)
    metric_passed = {
        name: sum(score.scores[name] == 1.0 for score in scores)
        for name in (
            "tool_contract",
            "authorization_safety",
            "idempotency_safety",
            "final_answer",
            "tool_budget",
            "workflow_lineage",
            "task_success",
        )
    }
    invalid_output_count = sum("model_output_invalid" in run.errors for run in runs)
    phoenix_trace_ids = {
        run.sample_id: run.phoenix_trace_id
        for run in runs
        if run.phoenix_trace_id is not None
    }
    phoenix_stored_trace_ids = verify_phoenix_traces(runs, run_id=run_id)
    trace_complete = (
        set(phoenix_trace_ids) == {case.sample_id for case in cases}
        and all(phoenix_trace_ids.values())
        and len(set(phoenix_trace_ids.values())) == len(cases)
        and phoenix_stored_trace_ids == phoenix_trace_ids
    )
    budget_summary = provider.budget.summary()
    monitoring_complete = (
        trace_complete
        and len(call_records)
        == response_receipt_count
        == budget_summary.get("request_count")
    )
    input_changed = _files_changed(source_paths, source_input_sha256)
    observed_status = (
        "complete"
        if (
            execution_error is None
            and len(scores) == len(cases)
            and monitoring_complete
            and not input_changed
        )
        else "partial"
        if scores
        else "inconclusive"
    )
    actual_models = sorted(
        {
            str(call["actual_model"])
            for call in call_records
            if call.get("actual_model") is not None
        }
    )
    provider_error_count, model_drift_count = summarize_call_failures(
        call_records, provider.expected_actual_model
    )
    error_type = (
        call_records[-1].get("error_type") if call_records else None
    ) or (type(execution_error).__name__ if execution_error else None)
    if error_type is None and input_changed:
        error_type = "InputChangedDuringRun"
    elif error_type is None and not trace_complete:
        error_type = "PhoenixTraceIncomplete"
    elif error_type is None and not monitoring_complete:
        error_type = "ProviderEvidenceIncomplete"
    agent_observed_status = (
        "complete"
        if execution_error is None and len(scores) == len(cases) and not input_changed
        else "partial"
        if scores
        else "inconclusive"
    )
    agent_safety_status = _classify_agent_safety(
        observed_status=agent_observed_status,
        passed=passed,
        total=len(cases),
        provider_error_count=provider_error_count,
        model_identity_matches=actual_models == [provider.expected_actual_model],
        input_changed=input_changed,
    )
    component_statuses = {
        "agent_safety": agent_safety_status,
        "monitoring": "pass" if monitoring_complete else "inconclusive",
    }
    if upstream_answer_quality is not None:
        component_statuses = {
            "upstream_answer_quality": upstream_answer_quality["status"],
            **component_statuses,
        }
    status = _combine_component_statuses(component_statuses)
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": status,
                "observed_status": observed_status,
                "profile": args.profile,
                "evidence_kind": "live_quality",
                "run_id": run_id,
                "trial_ids": trial_ids,
                "started_at_utc": started_at.isoformat(),
                "finished_at_utc": datetime.now(UTC).isoformat(),
                "git_sha": git_sha,
                "dataset": source_manifest,
                "upstream_sample_id": upstream_context.sample_id,
                "upstream_family_id": upstream_context.family_id,
                "upstream_selected_prompt_sha256": (
                    upstream_context.selected_prompt_sha256
                ),
                "upstream_selection_summary_sha256": (
                    upstream_context.selection_summary_sha256
                ),
                "upstream_source_summary_sha256": (
                    upstream_context.source_summary_sha256
                ),
                "upstream_responses_sha256": upstream_context.responses_sha256,
                "upstream_output_sha256": upstream_context.output_sha256,
                "requested_model": provider.model,
                "expected_actual_model": provider.expected_actual_model,
                "actual_models": actual_models,
                "model_drift_count": model_drift_count,
                "provider_error_count": provider_error_count,
                "invalid_output_count": invalid_output_count,
                "error_type": error_type,
                "structured_output": provider.structured_output,
                "max_retries": settings.limits.max_retries,
                "catalog_verified_on": args.catalog_verified_on.isoformat(),
                "pricing_verified_on": args.pricing_verified_on.isoformat(),
                "provider_config_sha256": source_input_sha256["provider-config.yaml"],
                "lockfile_sha256": source_input_sha256["uv.lock"],
                "runner_sha256": source_input_sha256["run-agent-live.py"],
                "case_sha256": source_input_sha256["agent-cases.yaml"],
                "prompt_sha256": source_input_sha256["agent-prompt.md"],
                "schema_sha256": source_input_sha256["agent-schema.py"],
                "scorer_sha256": source_input_sha256["agent-scorer.py"],
                "source_input_sha256": source_input_sha256,
                "input_changed_during_run": input_changed,
                "artifact_sha256": {
                    "calls.jsonl": _sha256(calls_path) if calls_path.is_file() else None,
                    "response-receipts.jsonl": (
                        _sha256(receipts_path) if receipts_path.is_file() else None
                    ),
                    "runs.jsonl": _sha256(args.output / "runs.jsonl"),
                    "scores.jsonl": _sha256(args.output / "scores.jsonl"),
                    **(
                        {"partial-runs.jsonl": _sha256(partial_runs_path)}
                        if partial_runs_path.is_file()
                        else {}
                    ),
                },
                "sample_ids": [case.sample_id for case in cases],
                "source_sample_ids": [case.source_sample_id for case in cases],
                "high_risk_sample_ids": [
                    case.sample_id for case in cases if case.risk_level == "high"
                ],
                "fault_seeds": {
                    case.sample_id: case.fault_seed
                    for case in cases
                    if case.fault_seed is not None
                },
                "target_count": len(cases),
                "record_count": len(scores),
                "target_sample_ids": [case.sample_id for case in cases],
                "completed_sample_ids": [score.sample_id for score in scores],
                "passed": passed,
                "total": len(cases),
                "metric_passed": metric_passed,
                "metric_record_count": len(scores),
                "judge_status": "not_requested",
                "human_review_status": "not_performed",
                "component_statuses": component_statuses,
                "agent_safety_status": agent_safety_status,
                **(
                    {
                        "upstream_answer_quality_status": upstream_answer_quality[
                            "status"
                        ],
                        "upstream_answer_quality_reason": upstream_answer_quality[
                            "reason"
                        ],
                        "upstream_evaluation_sha256": source_input_sha256[
                            "upstream-evaluation.json"
                        ],
                        "upstream_evaluation_manifest_sha256": source_input_sha256[
                            "upstream-evaluation-manifest.json"
                        ],
                    }
                    if upstream_answer_quality is not None
                    else {
                        "release_config_sha256": source_input_sha256[
                            "release-config.yaml"
                        ]
                    }
                ),
                "budget": budget_summary,
                "trace_complete": trace_complete,
                "monitoring_status": (
                    "complete" if monitoring_complete else "inconclusive"
                ),
                "phoenix_trace_count": len(phoenix_stored_trace_ids),
                "phoenix_allocated_trace_count": len(phoenix_trace_ids),
                "phoenix_stored_trace_ids": phoenix_stored_trace_ids,
                "phoenix_trace_ids": phoenix_trace_ids,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"status={status}, observed_status={observed_status}, 통과={passed}/{len(cases)}")
    if execution_error:
        print(f"실행 오류={type(execution_error).__name__}")
    return 0 if observed_status == "complete" and status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
