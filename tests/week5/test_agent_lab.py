from pathlib import Path

from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    load_agent_cases,
    load_lookup_records,
    run_cases,
)


def test_six_recorded_cases_pass(project_root: Path) -> None:
    cases = load_agent_cases(project_root / "data/agent/week-05-cases.yaml")
    runs, scores = run_cases(
        cases,
        RecordedAgentProvider(project_root / "data/recorded/week-05-agent-turns.jsonl"),
        prompt=(project_root / "prompts/week-05-agent.md").read_text(encoding="utf-8"),
        records=load_lookup_records(project_root / "data/agent/week-05-lookup.yaml"),
    )

    assert len(runs) == 6
    assert all(score.status == "passed" for score in scores)
    retry = next(run for run in runs if run.sample_id == "W5-06-idempotent-retry")
    assert retry.final_state["ticket_count"] == 1
    assert [item["event"] for item in retry.trace].count("tool_error") == 1
    assert any(item.get("result", {}).get("replayed") for item in retry.trace)


def test_pii_case_calls_no_tool(project_root: Path) -> None:
    case = next(
        item
        for item in load_agent_cases(project_root / "data/agent/week-05-cases.yaml")
        if item.sample_id == "W5-05-pii-denial"
    )
    runs, scores = run_cases(
        [case],
        RecordedAgentProvider(project_root / "data/recorded/week-05-agent-turns.jsonl"),
        prompt="safe agent",
        records=load_lookup_records(project_root / "data/agent/week-05-lookup.yaml"),
    )

    assert runs[0].tool_calls == []
    assert runs[0].final_answer.abstained
    assert scores[0].scores["authorization_safety"] == 1
