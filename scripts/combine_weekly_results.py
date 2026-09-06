"""weekly OpenCQA 이미지 5건·agent 6건을 AND gate로 합친다."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from verifiable_ai_workflow.agent_lab import load_agent_cases
from verifiable_ai_workflow.comparison import sha256_file
from verifiable_ai_workflow.release_monitoring import (
    combine_weekly_results,
    require_bound_artifact,
)
from verifiable_ai_workflow.schemas.agent import structured_answer_sha256
from verifiable_ai_workflow.schemas.models import StructuredAnswer

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, default=None):
    if not path.is_file() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _original_output_sha256(path: Path) -> str:
    originals = [row for row in _load_jsonl(path) if row.get("variant_id") == "original"]
    if len(originals) != 1:
        raise ValueError("robustness responses에는 original 출력이 정확히 한 건 필요합니다")
    try:
        output = StructuredAnswer.model_validate(originals[0].get("output"))
    except Exception as exc:
        raise ValueError("robustness original 출력이 구조화 답 형식과 다릅니다") from exc
    return structured_answer_sha256(output)


def _require_manifest_hash(manifest: dict, key: str, path: Path) -> None:
    expected = manifest.get(key)
    if not isinstance(expected, str) or expected != sha256_file(path):
        raise ValueError(f"evaluation manifest의 {key}가 현재 파일과 다릅니다")


def _load_agent_summary(args) -> dict:
    if args.agent_summary.is_file():
        return _load(args.agent_summary)
    partial_paths = (
        args.agent_calls,
        args.agent_scores,
        args.agent_summary.parent / "runs.jsonl",
    )
    if any(path.exists() for path in partial_paths):
        raise ValueError("agent summary 없이 일부 실행 파일만 남았습니다")
    raise ValueError("agent summary가 필요합니다")


def _validate_source_artifacts(
    args,
    robustness: dict,
    agent: dict,
    selection: dict,
) -> dict[str, str]:
    variant_root = PROJECT_ROOT / "local-data/opencqa/week-04-variants"
    cases_path = PROJECT_ROOT / "local-data/opencqa/week-03-cases.jsonl"
    robustness_paths = {
        "calls.jsonl": args.robustness_calls,
        "responses.jsonl": args.robustness_summary.parent / "responses.jsonl",
        "week-03-cases.jsonl": cases_path,
        "case.json": variant_root / "case.json",
        "variants.jsonl": variant_root / "variants.jsonl",
        "variant-review.csv": variant_root / "variant-review.csv",
    }
    for name, path in robustness_paths.items():
        require_bound_artifact(
            robustness,
            name,
            path,
            required=(name not in {"calls.jsonl", "responses.jsonl"})
            or robustness.get("status") != "inconclusive",
        )

    evaluation_manifest_path = args.robustness_scores.parent / "evaluation-manifest.json"
    evaluation_required = robustness.get("status") != "inconclusive"
    if evaluation_required or args.robustness_scores.exists() or evaluation_manifest_path.exists():
        if not args.robustness_scores.is_file() or not evaluation_manifest_path.is_file():
            raise ValueError("robustness evaluation과 manifest가 모두 필요합니다")
        evaluation_manifest = _load(evaluation_manifest_path)
        if evaluation_manifest.get("source_git_sha") != robustness.get("git_sha"):
            raise ValueError("robustness evaluation과 source 실행의 Git SHA가 다릅니다")
        if evaluation_manifest.get("schema_sha256") != robustness.get("schema_sha256"):
            raise ValueError("robustness 실행과 evaluation의 schema hash가 다릅니다")
        for key, path in {
            "evaluation_sha256": args.robustness_scores,
            "responses_sha256": robustness_paths["responses.jsonl"],
            "case_sha256": robustness_paths["case.json"],
            "variants_sha256": robustness_paths["variants.jsonl"],
            "reviews_sha256": robustness_paths["variant-review.csv"],
            "scorer_sha256": PROJECT_ROOT / "src/verifiable_ai_workflow/image_robustness.py",
            "metric_sha256": PROJECT_ROOT / "src/verifiable_ai_workflow/prompt_optimization.py",
            "schema_sha256": PROJECT_ROOT / "src/verifiable_ai_workflow/schemas/models.py",
        }.items():
            _require_manifest_hash(evaluation_manifest, key, path)

    agent_required = agent.get("status") != "inconclusive"
    for name, path in {
        "calls.jsonl": args.agent_calls,
        "runs.jsonl": args.agent_summary.parent / "runs.jsonl",
        "scores.jsonl": args.agent_scores,
    }.items():
        require_bound_artifact(agent, name, path, required=agent_required)

    for name, path in {
        "calls.jsonl": args.prompt_selection_summary.parent / "calls.jsonl",
        "validation.jsonl": args.prompt_selection_summary.parent / "validation.jsonl",
        "selected-prompt.md": args.selected_prompt,
        "week-03-cases.jsonl": cases_path,
    }.items():
        require_bound_artifact(selection, name, path, required=True)

    expected_agent_upstream = {
        "upstream_source_summary_sha256": sha256_file(args.robustness_summary),
        "upstream_responses_sha256": sha256_file(robustness_paths["responses.jsonl"]),
        "upstream_output_sha256": _original_output_sha256(
            robustness_paths["responses.jsonl"]
        ),
        "upstream_selection_summary_sha256": sha256_file(args.prompt_selection_summary),
    }
    if any(agent.get(name) != expected for name, expected in expected_agent_upstream.items()):
        raise ValueError("agent summary의 Week 4 upstream 파일 계보가 실제 파일과 다릅니다")

    source_paths = {
        "robustness_summary": args.robustness_summary,
        "robustness_calls": args.robustness_calls,
        "robustness_scores": args.robustness_scores,
        "agent_summary": args.agent_summary,
        "agent_calls": args.agent_calls,
        "agent_scores": args.agent_scores,
        "prompt_selection_summary": args.prompt_selection_summary,
        "selected_prompt": args.selected_prompt,
    }
    return {name: sha256_file(path) for name, path in source_paths.items() if path.is_file()}


def _clean_git_sha() -> str:
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise SystemExit("weekly 결과 결합은 변경사항이 없는 Git commit에서만 허용합니다")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robustness-summary", type=Path, required=True)
    parser.add_argument("--robustness-calls", type=Path, required=True)
    parser.add_argument("--robustness-scores", type=Path, required=True)
    parser.add_argument("--agent-summary", type=Path, required=True)
    parser.add_argument("--agent-calls", type=Path, required=True)
    parser.add_argument("--agent-scores", type=Path, required=True)
    parser.add_argument("--prompt-selection-summary", type=Path, required=True)
    parser.add_argument("--selected-prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    robustness = _load(args.robustness_summary)
    selection = _load(args.prompt_selection_summary)
    selection["selection_summary_sha256"] = sha256_file(args.prompt_selection_summary)
    agent_cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    agent = _load_agent_summary(args)
    source_artifact_sha256 = _validate_source_artifacts(
        args, robustness, agent, selection
    )
    summary = combine_weekly_results(
        robustness,
        _load(args.robustness_scores, []),
        agent,
        _load_jsonl(args.agent_scores),
        expected_agent_ids=[case.sample_id for case in agent_cases],
        expected_high_risk_ids=[
            case.sample_id for case in agent_cases if case.risk_level == "high"
        ],
        selected_prompt_sha256=sha256_file(args.selected_prompt),
        prompt_selection=selection,
        evaluator_git_sha=_clean_git_sha(),
    )
    args.output.mkdir(parents=True, exist_ok=False)
    calls_path = args.output / "calls.jsonl"
    with calls_path.open("w", encoding="utf-8") as target:
        for source in (args.robustness_calls, args.agent_calls):
            if source.is_file():
                target.write(source.read_text(encoding="utf-8"))
    summary["source_artifact_sha256"] = source_artifact_sha256
    summary["release_config_sha256"] = sha256_file(PROJECT_ROOT / "configs/week-06.yaml")
    summary["artifact_sha256"] = {"calls.jsonl": sha256_file(calls_path)}
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
