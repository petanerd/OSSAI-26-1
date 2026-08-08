"""Week 5 사례, 저장 turn과 DeepEval 결과 기록을 연결한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from deepeval import evaluate
from deepeval.evaluate import AsyncConfig, CacheConfig, DisplayConfig
from deepeval.test_case import LLMTestCase

from .evaluation.agent_scoring import score_agent_run
from .evaluation.deepeval_runner import ResultMetric
from .schemas.agent import AgentCase, AgentRun, AgentScore, AgentTurn
from .workflow.agent_runner import run_agent_case


def load_agent_cases(path: str | Path) -> list[AgentCase]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases = [AgentCase.model_validate(item) for item in payload["cases"]]
    if len(cases) != 6 or len({case.sample_id for case in cases}) != 6:
        raise ValueError("Week 5 핵심 사례는 중복 없는 6개여야 합니다")
    return cases


def load_lookup_records(path: str | Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["records"]


class RecordedAgentProvider:
    evidence_kind = "test_only"

    def __init__(self, path: str | Path) -> None:
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        self.turns = {row["sample_id"]: row["turns"] for row in rows}
        self.index = {sample_id: 0 for sample_id in self.turns}

    def generate(self, sample_id, messages, *, response_schema=AgentTurn):
        del messages
        index = self.index[sample_id]
        try:
            turn = self.turns[sample_id][index]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"저장 turn이 부족합니다: {sample_id}") from exc
        self.index[sample_id] += 1
        return response_schema.model_validate(turn).model_dump_json()


def run_cases(
    cases: list[AgentCase],
    provider,
    *,
    prompt: str,
    records: dict[str, dict[str, Any]],
) -> tuple[list[AgentRun], list[AgentScore]]:
    runs = [
        run_agent_case(case, provider, system_prompt=prompt, records=records) for case in cases
    ]
    return runs, [score_agent_run(case, run) for case, run in zip(cases, runs, strict=True)]


def record_with_deepeval(
    cases: list[AgentCase],
    runs: list[AgentRun],
    scores: list[AgentScore],
    output_dir: str | Path,
) -> None:
    test_cases = [
        LLMTestCase(
            name=case.sample_id,
            input=case.instruction,
            actual_output=run.model_dump_json(),
            expected_output=json.dumps(
                {
                    "calls": [call.model_dump(mode="json") for call in case.expected_calls],
                    "ticket_count": case.expected_ticket_count,
                    "abstained": case.expected_abstained,
                },
                ensure_ascii=False,
            ),
        )
        for case, run in zip(cases, runs, strict=True)
    ]
    metric = ResultMetric(
        "task_success",
        "Agent 전체 성공",
        {score.sample_id: score.scores["task_success"] for score in scores},
        {score.sample_id: score.reasons["task_success"] for score in scores},
        threshold=1.0,
    )
    evaluate(
        test_cases=test_cases,
        metrics=[metric],
        async_config=AsyncConfig(run_async=False),
        cache_config=CacheConfig(write_cache=False, use_cache=False),
        display_config=DisplayConfig(
            show_indicator=False,
            print_results=False,
            inspect_after_run=False,
            results_folder=str(output_dir),
        ),
    )
