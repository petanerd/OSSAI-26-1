"""DeepEval PromptOptimizer(GEPA)로 prompt를 만들고 validation 6개에서 비교한다."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from deepeval.prompt import Prompt

from verifiable_ai_workflow.config.secrets import load_project_env
from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.course_live import build_course_provider
from verifiable_ai_workflow.judge_calibration import load_pairs
from verifiable_ai_workflow.judge_model import CourseJudgeModel
from verifiable_ai_workflow.live_execution import LiveBudgetCaps
from verifiable_ai_workflow.prompt_optimization import (
    OpenCqaDeterministicMetric,
    OpenCqaVlmCallback,
    build_prompt_optimizer,
    score_output,
    split_goldens,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _clean_git() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status.strip():
        raise SystemExit("PromptOptimizer 실제 실행은 변경사항이 없는 Git commit에서만 허용합니다")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-optimize", action="store_true")
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live_optimize:
        raise SystemExit("실제 최적화에는 --live-optimize가 필요합니다")
    git_sha = _clean_git()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    caps = LiveBudgetCaps(
        max_requests=args.max_requests,
        max_attempts=args.max_requests,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_cost_usd=args.max_cost_usd,
        max_wall_seconds=args.max_wall_seconds,
    )
    settings = load_settings(PROJECT_ROOT / "configs/nvidia-nim-gemma4.yaml")
    load_project_env(PROJECT_ROOT)
    calls_path = args.output / "calls.jsonl"

    def record_call(call: dict) -> None:
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")

    provider = build_course_provider(settings, caps, on_response=record_call)
    callback = OpenCqaVlmCallback(provider, PROJECT_ROOT)
    splits = split_goldens(
        load_pairs(PROJECT_ROOT / "local-data/opencqa/week-03-pairs.jsonl")
    )
    baseline = Prompt(
        text_template=(PROJECT_ROOT / "prompts/week-04-baseline.md").read_text(encoding="utf-8")
    )
    optimizer = build_prompt_optimizer(
        goldens=splits["development"],
        model_callback=callback,
        optimizer_model=CourseJudgeModel(provider),
        config_path=PROJECT_ROOT / "configs/week-04.yaml",
    )
    candidate = optimizer.optimize(baseline, splits["development"])
    (args.output / "candidate-prompt.md").write_text(
        candidate.text_template or "",
        encoding="utf-8",
    )

    metric = OpenCqaDeterministicMetric()
    records: list[dict] = []
    for golden in splits["validation"]:
        for name, prompt in (("baseline", baseline), ("candidate", candidate)):
            output = callback(prompt, golden)
            records.append(
                {
                    "prompt": name,
                    "output": output,
                    **score_output(metric, golden, output),
                }
            )
    (args.output / "validation.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )

    def mean(name: str) -> float:
        values = [item["score"] for item in records if item["prompt"] == name]
        return sum(values) / len(values)

    baseline_mean, candidate_mean = mean("baseline"), mean("candidate")
    summary = {
        "status": "completed",
        "evidence_kind": "live_quality",
        "git_sha": git_sha,
        "development_count": 18,
        "validation_count": 6,
        "test_opened": False,
        "baseline_mean": baseline_mean,
        "candidate_mean": candidate_mean,
        "selected": "candidate" if candidate_mean > baseline_mean else "baseline",
        "budget": provider.budget.summary(),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"validation 평균 baseline={baseline_mean:.3f}, candidate={candidate_mean:.3f}, "
        f"선택={summary['selected']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
