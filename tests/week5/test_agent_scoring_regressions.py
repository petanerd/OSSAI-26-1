"""실제 도구 실패와 숫자·ID 부분 일치가 통과하지 않는지 저장 응답으로 검사한다."""

from copy import deepcopy
from pathlib import Path

import pytest

from verifiable_ai_workflow.agent_lab import (
    RecordedAgentProvider,
    load_agent_cases,
    load_agent_upstream_context,
    load_lookup_records,
    run_cases,
)
from verifiable_ai_workflow.evaluation.agent_scoring import _contains_fact, score_agent_run
from verifiable_ai_workflow.schemas.agent import AgentFinal


@pytest.fixture
def recorded_cases(project_root: Path):
    cases = load_agent_cases(project_root / "data/agent/week-05-cases.yaml")
    runs, scores = run_cases(
        cases,
        RecordedAgentProvider(project_root / "data/recorded/week-05-agent-turns.jsonl"),
        upstream_context=load_agent_upstream_context(
            project_root / "data/recorded/week-05-upstream.json"
        ),
        prompt="저장 응답 채점 검사",
        records=load_lookup_records(project_root / "data/agent/week-05-lookup.yaml"),
    )
    assert all(score.status == "passed" for score in scores)
    return {case.sample_id: (case, run) for case, run in zip(cases, runs, strict=True)}


def test_failed_lookup_does_not_pass_with_expected_final_text(project_root: Path) -> None:
    case = load_agent_cases(project_root / "data/agent/week-05-cases.yaml")[2]
    runs, scores = run_cases(
        [case],
        RecordedAgentProvider(project_root / "data/recorded/week-05-agent-turns.jsonl"),
        upstream_context=load_agent_upstream_context(
            project_root / "data/recorded/week-05-upstream.json"
        ),
        prompt="조회 실패 재현",
        records={},
    )
    assert runs[0].ledger[0]["status"] == "error"
    assert runs[0].ledger[0]["error_type"] == "ToolError"
    assert scores[0].scores["final_answer"] == 1
    assert scores[0].scores["tool_contract"] == 0
    assert scores[0].status == "failed"
    assert "ToolError" in scores[0].reasons["tool_contract"]


@pytest.mark.parametrize(
    "fault", ["missing_ledger", "wrong_record", "missing_field", "null_values", "empty_values"]
)
def test_lookup_requires_matching_successful_receipt(recorded_cases, fault: str) -> None:
    case, run = recorded_cases["W5-03-lookup"]
    ledger = deepcopy(run.ledger)
    if fault == "missing_ledger":
        ledger.clear()
    elif fault == "wrong_record":
        ledger[0]["result"]["record_id"] = "other-record"
    elif fault == "missing_field":
        ledger[0]["result"]["fields"].pop("updated_at")
    else:
        value = None if fault == "null_values" else " "
        ledger[0]["result"]["fields"] = {"status": value, "updated_at": value}
    score = score_agent_run(case, run.model_copy(update={"ledger": ledger}))
    assert score.scores["tool_contract"] == 0
    assert score.status == "failed"


@pytest.mark.parametrize(
    ("sample_id", "answer", "expected_status"),
    [
        ("W5-01-direct", "auspol은 186%입니다.", "failed"),
        ("W5-01-direct", "auspol은 86,000%입니다.", "failed"),
        ("W5-01-direct", "auspol은 86abc%입니다.", "failed"),
        ("W5-01-direct", "auspol은 86.5%입니다.", "failed"),
        ("W5-01-direct", "auspol은 -86%입니다.", "failed"),
        ("W5-01-direct", "auspol은 −86%입니다.", "failed"),
        ("W5-01-direct", "auspol은 86.0 %입니다.", "passed"),
        ("W5-01-direct", "auspol은 ８６％입니다.", "passed"),
        ("W5-02-calculator", "차이는 125입니다.", "failed"),
        ("W5-02-calculator", "차이는 250입니다.", "failed"),
        ("W5-02-calculator", "차이는 25,000입니다.", "failed"),
        ("W5-02-calculator", "차이는 25.1입니다.", "failed"),
        ("W5-02-calculator", "차이는 25e3입니다.", "failed"),
        ("W5-02-calculator", "차이는 25abc입니다.", "failed"),
        ("W5-02-calculator", "차이는 25.0%p입니다.", "passed"),
        # 단위 검사는 이번 수정 범위 밖이다. 과거 25% false pass를 소급 변경하지 않는다.
        ("W5-02-calculator", "차이는 25%입니다.", "passed"),
        ("W5-04-ticket", "TICKET-00010을 생성했습니다.", "failed"),
        ("W5-04-ticket", "TICKET-0001A를 생성했습니다.", "failed"),
        ("W5-04-ticket", "XTICKET-0001을 생성했습니다.", "failed"),
        ("W5-04-ticket", "`ticket-0001`을 생성했습니다.", "passed"),
        ("W5-06-idempotent-retry", "TICKET-00010 한 건입니다.", "failed"),
    ],
)
def test_final_numbers_and_ids_are_not_substrings(
    recorded_cases, sample_id: str, answer: str, expected_status: str,
) -> None:
    case, run = recorded_cases[sample_id]
    final = AgentFinal(answer=answer, abstained=False, abstention_reason=None)
    score = score_agent_run(case, run.model_copy(update={"final_answer": final}))
    assert score.status == expected_status
    assert score.scores["final_answer"] == (1 if expected_status == "passed" else 0)
    assert score.scores["tool_contract"] == 1
    assert score.scores["idempotency_safety"] == 1


def test_expected_after_commit_timeout_still_passes(recorded_cases) -> None:
    case, run = recorded_cases["W5-06-idempotent-retry"]
    assert [entry["status"] for entry in run.ledger] == ["error", "success"]
    assert run.ledger[0]["error_type"] == "AfterCommitTimeout"
    assert run.final_state["ticket_count"] == 1
    assert score_agent_run(case, run).status == "passed"


@pytest.mark.parametrize("answer", ["86,000", "86abc", "abc86", "0x86"])
def test_number_must_be_a_complete_token(answer: str) -> None:
    assert not _contains_fact(answer, "86")


def test_lookup_date_allows_iso_time_but_not_extended_date(recorded_cases) -> None:
    case, run = recorded_cases["W5-03-lookup"]
    for timestamp, expected_status in (
        ("2026-08-07T09:00:00Z", "passed"),
        ("2026-08-070T09:00:00Z", "failed"),
    ):
        final = AgentFinal(
            answer=f"OpenCQA 884의 상태는 operational, 갱신 시각은 {timestamp}입니다.",
            abstained=False,
            abstention_reason=None,
        )
        score = score_agent_run(case, run.model_copy(update={"final_answer": final}))
        assert score.status == expected_status
