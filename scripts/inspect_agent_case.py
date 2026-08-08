"""Week 5 사례 하나의 model turn, 도구 결과와 점수를 출력한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    load_agent_cases,
    load_lookup_records,
    run_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-id", default="W5-06-idempotent-retry")
    args = parser.parse_args()
    cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    try:
        case = next(item for item in cases if item.sample_id == args.sample_id)
    except StopIteration as exc:
        raise SystemExit(f"알 수 없는 sample ID: {args.sample_id}") from exc
    runs, scores = run_cases(
        [case],
        RecordedAgentProvider(PROJECT_ROOT / "data/recorded/week-05-agent-turns.jsonl"),
        prompt=(PROJECT_ROOT / "prompts/week-05-agent.md").read_text(encoding="utf-8"),
        records=load_lookup_records(PROJECT_ROOT / "data/agent/week-05-lookup.yaml"),
    )
    print(
        json.dumps(
            {
                "instruction": case.instruction,
                "authorization": case.authorization.model_dump(mode="json"),
                "expected_calls": [item.model_dump(mode="json") for item in case.expected_calls],
                "trace": runs[0].trace,
                "final_state": runs[0].final_state,
                "scores": scores[0].model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
