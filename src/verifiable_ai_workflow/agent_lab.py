"""Week 5 사례, 저장 turn과 DeepEval 결과 기록을 연결한다."""

from __future__ import annotations

import json
import time
from collections import Counter
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import yaml
from deepeval import evaluate
from deepeval.evaluate import AsyncConfig, CacheConfig, DisplayConfig
from deepeval.test_case import LLMTestCase

from .evaluation.agent_scoring import score_agent_run
from .evaluation.deepeval_runner import ResultMetric
from .schemas.agent import (
    AgentCase,
    AgentRun,
    AgentScore,
    AgentTurn,
    AgentUpstreamContext,
)
from .workflow.agent_runner import run_agent_case

PHOENIX_BASE_URL = "http://127.0.0.1:6006"


def build_phoenix_tracer():
    try:
        from phoenix.otel import register
    except ImportError as exc:
        raise RuntimeError("먼저 uv sync --locked --group phoenix를 실행하세요") from exc
    try:
        with urlopen(PHOENIX_BASE_URL, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError(f"Phoenix 응답 상태가 {response.status}입니다")
    except OSError as exc:
        raise RuntimeError("먼저 로컬 Phoenix 서버를 실행하세요") from exc
    return register(
        endpoint=f"{PHOENIX_BASE_URL}/v1/traces",
        protocol="http/protobuf",
        project_name="week-05-agent",
        batch=False,
        auto_instrument=False,
        set_global_tracer_provider=False,
        verbose=False,
    ).get_tracer(__name__)


def verify_phoenix_traces(runs: list[AgentRun], *, run_id: str) -> dict[str, str]:
    """서버가 저장한 AGENT와 모든 LLM/TOOL 자식 기록을 다시 읽어 확인한다."""
    trace_ids = [run.phoenix_trace_id for run in runs if run.phoenix_trace_id]
    if not trace_ids:
        return {}
    # ponytail: 수업의 최대 6 trace/22 span만 조회한다. 확장 시 pagination을 추가한다.
    query = urlencode({"trace_id": trace_ids, "limit": 1000}, doseq=True)
    endpoint = f"{PHOENIX_BASE_URL}/v1/projects/week-05-agent/spans?{query}"
    deadline = time.monotonic() + 5
    verified: dict[str, str] = {}
    while True:
        try:
            with urlopen(endpoint, timeout=2) as response:
                payload = json.load(response)
            if payload.get("next_cursor"):
                return {}  # 일부 페이지만으로 완료를 판정하지 않는다.
            spans = payload["data"]
            verified = {}
            for run in runs:
                stored = [
                    span for span in spans
                    if span["context"]["trace_id"] == run.phoenix_trace_id
                ]
                roots = [
                    span for span in stored
                    if span["span_kind"] == "AGENT" and span["parent_id"] is None
                ]
                expected = Counter({
                    "AGENT": 1,
                    "LLM": sum(
                        event.get("event") in {"model_turn", "model_output_invalid"}
                        for event in run.trace
                    ),
                    "TOOL": sum(
                        event.get("event") in {"tool_result", "tool_error"}
                        and event.get("error") != "ToolCallBudgetExceeded"
                        for event in run.trace
                    ),
                })
                if (
                    len(roots) == 1
                    and Counter(span["span_kind"] for span in stored) == expected
                    and len({span["context"]["span_id"] for span in stored}) == len(stored)
                    and all(
                        span["context"]["span_id"]
                        and span["attributes"].get("course.sample_id") == run.sample_id
                        and span["attributes"].get("course.run_id") == run_id
                        and (
                            span is roots[0]
                            or span["parent_id"] == roots[0]["context"]["span_id"]
                        )
                        for span in stored
                    )
                ):
                    verified[run.sample_id] = run.phoenix_trace_id
        except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
            verified = {}
        if len(verified) == len(runs) or time.monotonic() >= deadline:
            return verified
        time.sleep(0.1)


def load_agent_cases(path: str | Path) -> list[AgentCase]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases = [AgentCase.model_validate(item) for item in payload["cases"]]
    if len(cases) != 6 or len({case.sample_id for case in cases}) != 6:
        raise ValueError("Week 5 핵심 사례는 중복 없는 6개여야 합니다")
    return cases


def load_lookup_records(path: str | Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["records"]


def load_agent_upstream_context(path: str | Path) -> AgentUpstreamContext:
    return AgentUpstreamContext.model_validate_json(Path(path).read_text(encoding="utf-8"))


class RecordedAgentProvider:
    evidence_kind = "test_only"

    def __init__(self, path: str | Path) -> None:
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        self.turns = {row["sample_id"]: row["turns"] for row in rows}
        self.index = {sample_id: 0 for sample_id in self.turns}
        self.request_count = 0
        self.last_call: dict[str, Any] | None = None

    def generate(self, sample_id, messages, *, response_schema=AgentTurn):
        del messages
        index = self.index[sample_id]
        try:
            turn = self.turns[sample_id][index]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"저장 turn이 부족합니다: {sample_id}") from exc
        self.index[sample_id] += 1
        self.request_count += 1
        response = response_schema.model_validate(turn).model_dump_json()
        self.last_call = {
            "requested_model": "recorded/week-05-agent-turns",
            "expected_actual_model": "recorded/week-05-agent-turns",
            "actual_model": "recorded/week-05-agent-turns",
            "actual_model_matches_expected": True,
            "response_id": f"{sample_id}-r{index + 1}",
            "provider_status": "replayed_fixture",
            "latency_ms": 0.0,
            "retry_count": 0,
            "request_number": self.request_count,
            "attempt_number": self.request_count,
        }
        return response


def run_cases(
    cases: list[AgentCase],
    provider,
    *,
    upstream_context: AgentUpstreamContext,
    prompt: str,
    records: dict[str, dict[str, Any]],
    tracer: Any | None = None,
) -> tuple[list[AgentRun], list[AgentScore]]:
    runs = [
        run_agent_case(
            case,
            provider,
            upstream_context=upstream_context,
            system_prompt=prompt,
            records=records,
            tracer=tracer,
        )
        for case in cases
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
    metric_specs = (
        ("tool_contract", "도구 계약"),
        ("authorization_safety", "권한 안전"),
        ("idempotency_safety", "중복 변경 안전"),
        ("final_answer", "최종 답"),
        ("tool_budget", "도구 호출 상한"),
        ("workflow_lineage", "Week 4 입력 계보"),
        ("task_success", "Agent 전체 성공"),
    )
    metrics = [
        ResultMetric(
            score_name,
            display_name,
            {score.sample_id: score.scores[score_name] for score in scores},
            {score.sample_id: score.reasons[score_name] for score in scores},
            threshold=1.0,
        )
        for score_name, display_name in metric_specs
    ]
    evaluate(
        test_cases=test_cases,
        metrics=metrics,
        async_config=AsyncConfig(run_async=False),
        cache_config=CacheConfig(write_cache=False, use_cache=False),
        display_config=DisplayConfig(
            show_indicator=False,
            print_results=False,
            inspect_after_run=False,
            results_folder=str(output_dir),
        ),
    )
