import json
from pathlib import Path

import pytest
from deepeval.models import DeepEvalBaseLLM
from deepeval.prompt import Prompt

from verifiable_ai_workflow.judge_calibration import JudgePair
from verifiable_ai_workflow.prompt_optimization import (
    OpenCqaDeterministicMetric,
    build_prompt_optimizer,
    score_output,
    split_goldens,
    validate_development_goldens,
)


class NoCallModel(DeepEvalBaseLLM):
    def load_model(self):
        return self

    def get_model_name(self, *args, **kwargs):
        return "no-call"

    def generate(self, *args, **kwargs):
        raise AssertionError("factory에서 model을 호출하면 안 됩니다")

    async def a_generate(self, *args, **kwargs):
        return self.generate(*args, **kwargs)


def _pairs() -> list[JudgePair]:
    return [
        JudgePair(
            pair_id=f"pair-{index}",
            sample_id=str(index),
            image_path=f"{index}.png",
            question="What changed?",
            reference_answer="It rose from 10% to 20%.",
            candidate_a="A",
            candidate_b="B",
        )
        for index in range(30)
    ]


def test_split_is_18_6_6_and_optimizer_uses_development(project_root: Path) -> None:
    splits = split_goldens(_pairs())

    assert {name: len(items) for name, items in splits.items()} == {
        "development": 18,
        "validation": 6,
        "test": 6,
    }
    optimizer = build_prompt_optimizer(
        goldens=splits["development"],
        model_callback=lambda prompt, golden: "{}",
        optimizer_model=NoCallModel(),
        config_path=project_root / "configs/week-04.yaml",
    )
    assert optimizer.algorithm.iterations == 2
    with pytest.raises(ValueError, match="development"):
        validate_development_goldens(splits["validation"])


def test_metric_returns_feedback_for_missing_number() -> None:
    golden = split_goldens(_pairs())["development"][0]
    output = json.dumps(
        {
            "answer": "It rose to 20%.",
            "evidence": [
                {"evidence_id": "chart#page=1", "quote": "20%", "page_number": 1}
            ],
            "confidence": 0.8,
            "abstained": False,
            "abstention_reason": None,
            "tool_requests": [],
        }
    )

    result = score_output(OpenCqaDeterministicMetric(), golden, output)

    assert 0 < result["score"] < 1
    assert "10%" in result["reason"]


def test_baseline_prompt_interpolates_question(project_root: Path) -> None:
    prompt = Prompt(text_template=(project_root / "prompts/week-04-baseline.md").read_text())
    assert "What changed?" in prompt.interpolate(question="What changed?")
