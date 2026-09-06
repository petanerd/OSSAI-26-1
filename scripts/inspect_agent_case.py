"""Week 5 사례 하나의 model turn, 도구 결과와 점수를 출력한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    load_agent_cases,
    load_agent_upstream_context,
    load_lookup_records,
    run_cases,
)
from verifiable_ai_workflow.evaluation.agent_scoring import score_agent_run
from verifiable_ai_workflow.schemas.agent import AgentRun

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _inject_safety_fault(run: AgentRun) -> AgentRun:
    return run.model_copy(
        update={
            "trace": [
                *run.trace,
                {"event": "tool_error", "tool": "lookup", "error": "AuthorizationDenied"},
            ],
            "final_state": {
                **run.final_state,
                "ticket_count": run.final_state["ticket_count"] + 1,
            },
            "errors": [*run.errors, "tool_call_budget_exceeded"],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-id", default="W5-06-idempotent-retry")
    parser.add_argument("--show-safety-fault", action="store_true")
    args = parser.parse_args()
    cases = load_agent_cases(PROJECT_ROOT / "data/agent/week-05-cases.yaml")
    try:
        case = next(item for item in cases if item.sample_id == args.sample_id)
    except StopIteration as exc:
        raise SystemExit(f"알 수 없는 sample ID: {args.sample_id}") from exc
    runs, scores = run_cases(
        [case],
        RecordedAgentProvider(PROJECT_ROOT / "data/recorded/week-05-agent-turns.jsonl"),
        upstream_context=load_agent_upstream_context(
            PROJECT_ROOT / "data/recorded/week-05-upstream.json"
        ),
        prompt=(PROJECT_ROOT / "prompts/week-05-agent.md").read_text(encoding="utf-8"),
        records=load_lookup_records(PROJECT_ROOT / "data/agent/week-05-lookup.yaml"),
    )
    run = _inject_safety_fault(runs[0]) if args.show_safety_fault else runs[0]
    score = score_agent_run(case, run) if args.show_safety_fault else scores[0]
    print(
        json.dumps(
            {
                "source_sample_id": case.source_sample_id,
                "family_id": case.family_id,
                "upstream_context": run.upstream_context.model_dump(mode="json"),
                "risk_level": case.risk_level,
                "instruction": case.instruction,
                "authorization": case.authorization.model_dump(mode="json"),
                "expected_calls": [item.model_dump(mode="json") for item in case.expected_calls],
                "fault_seed": case.fault_seed,
                "additional_safety_fault_injected": args.show_safety_fault,
                "final_answer": (
                    run.final_answer.model_dump(mode="json") if run.final_answer else None
                ),
                "trace": run.trace,
                "ledger": run.ledger,
                "errors": run.errors,
                "initial_state": run.initial_state,
                "final_state": run.final_state,
                "scores": score.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
