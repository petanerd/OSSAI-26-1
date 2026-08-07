"""Week 5 여섯 사례를 실제 task model과 로컬 도구 sandbox로 실행한다."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from verifiable_ai_workflow.agent_lab import (
    load_agent_cases,
    load_lookup_records,
    record_with_deepeval,
    run_cases,
)
from verifiable_ai_workflow.config.secrets import load_project_env
from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.course_live import build_course_provider
from verifiable_ai_workflow.live_execution import LiveBudgetCaps

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def required_live_requests() -> int:
    cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    return sum(case.max_tool_calls + 1 for case in cases)


def _git_sha() -> str:
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise SystemExit("Week 5 실제 실행은 변경사항이 없는 Git commit에서만 허용합니다")
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
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("실제 task model 호출에는 --live가 필요합니다")
    required = required_live_requests()
    if args.max_requests != required:
        raise SystemExit(f"여섯 사례 전체 실행에는 --max-requests {required}이 필요합니다")
    git_sha = _git_sha()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    caps = LiveBudgetCaps(
        max_requests=required,
        max_attempts=required,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_cost_usd=args.max_cost_usd,
        max_wall_seconds=args.max_wall_seconds,
    )
    load_project_env(PROJECT_ROOT)
    calls_path = args.output / "calls.jsonl"

    def record_call(call: dict) -> None:
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")

    provider = build_course_provider(
        load_settings(PROJECT_ROOT / "configs/nvidia-nim-gemma4.yaml"),
        caps,
        on_response=record_call,
    )
    cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    runs, scores = run_cases(
        cases,
        provider,
        prompt=(PROJECT_ROOT / "prompts/week-05-agent.md").read_text(encoding="utf-8"),
        records=load_lookup_records(PROJECT_ROOT / "data/agent/week-05-lookup.yaml"),
    )
    (args.output / "runs.jsonl").write_text(
        "".join(run.model_dump_json() + "\n" for run in runs), encoding="utf-8"
    )
    (args.output / "scores.jsonl").write_text(
        "".join(score.model_dump_json() + "\n" for score in scores), encoding="utf-8"
    )
    record_with_deepeval(cases, runs, scores, args.output / "deepeval")
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "evidence_kind": "live_quality",
                "git_sha": git_sha,
                "passed": sum(score.status == "passed" for score in scores),
                "total": len(scores),
                "budget": provider.budget.summary(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"통과={sum(score.status == 'passed' for score in scores)}/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
