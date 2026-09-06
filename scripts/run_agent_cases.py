"""저장된 model turn으로 Week 5 여섯 사례를 실행한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    build_phoenix_tracer,
    load_agent_cases,
    load_agent_upstream_context,
    load_lookup_records,
    record_with_deepeval,
    run_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "reports/week-05/offline"
    )
    parser.add_argument("--phoenix", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    runs, scores = run_cases(
        cases,
        RecordedAgentProvider(PROJECT_ROOT / "data/recorded/week-05-agent-turns.jsonl"),
        upstream_context=load_agent_upstream_context(
            PROJECT_ROOT / "data/recorded/week-05-upstream.json"
        ),
        prompt=(PROJECT_ROOT / "prompts/week-05-agent.md").read_text(encoding="utf-8"),
        records=load_lookup_records(PROJECT_ROOT / "data/agent/week-05-lookup.yaml"),
        tracer=build_phoenix_tracer() if args.phoenix else None,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "runs.jsonl").write_text(
        "".join(run.model_dump_json() + "\n" for run in runs), encoding="utf-8"
    )
    (args.output / "scores.jsonl").write_text(
        "".join(score.model_dump_json() + "\n" for score in scores), encoding="utf-8"
    )
    record_with_deepeval(cases, runs, scores, args.output / "deepeval")
    print(f"통과={sum(score.status == 'passed' for score in scores)}/6 (test_only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
