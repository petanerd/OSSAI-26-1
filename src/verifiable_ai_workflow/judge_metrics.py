"""OpenCQA 후보 비교에 필요한 DeepEval ArenaGEval 한 개만 만든다."""

from __future__ import annotations

from pathlib import Path

import yaml
from deepeval.metrics import ArenaGEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import ArenaTestCase, Contestant, LLMTestCase, SingleTurnParams

from .judge_calibration import JudgePair, Preference


def build_arena_metric(model: DeepEvalBaseLLM, rubric_path: str | Path) -> ArenaGEval:
    rubric = yaml.safe_load(Path(rubric_path).read_text(encoding="utf-8"))
    return ArenaGEval(
        name="OpenCQA Better Answer",
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        evaluation_steps=rubric["evaluation_steps"],
        model=model,
        async_mode=False,
    )


def build_arena_case(pair: JudgePair, *, reverse: bool = False) -> ArenaTestCase:
    contestants = [
        Contestant(
            name="candidate_a",
            test_case=LLMTestCase(
                input=pair.question,
                actual_output=pair.candidate_a,
                expected_output=pair.reference_answer,
            ),
        ),
        Contestant(
            name="candidate_b",
            test_case=LLMTestCase(
                input=pair.question,
                actual_output=pair.candidate_b,
                expected_output=pair.reference_answer,
            ),
        ),
    ]
    if reverse:
        contestants.reverse()
    return ArenaTestCase(contestants=contestants)


def measure(metric: ArenaGEval, pair: JudgePair, *, reverse: bool = False) -> Preference:
    try:
        winner = metric.measure(build_arena_case(pair, reverse=reverse), _show_indicator=False)
    except KeyError as exc:
        if exc.args != ("tie",):
            raise
        winner = "tie"
    if winner not in {"candidate_a", "tie", "candidate_b"}:
        raise ValueError(f"알 수 없는 Judge winner: {winner}")
    return winner
