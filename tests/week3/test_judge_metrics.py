from deepeval.models import DeepEvalBaseLLM

from verifiable_ai_workflow.judge_calibration import JudgePair
from verifiable_ai_workflow.judge_metrics import build_arena_case, build_arena_metric, measure


class NoCallJudge(DeepEvalBaseLLM):
    def load_model(self):
        return self

    def get_model_name(self, *args, **kwargs):
        return "no-call"

    def generate(self, *args, **kwargs):
        raise AssertionError("metric 생성 중 API를 호출하면 안 됩니다")

    async def a_generate(self, *args, **kwargs):
        return self.generate(*args, **kwargs)


def _pair() -> JudgePair:
    return JudgePair(
        pair_id="pair-1",
        sample_id="1",
        image_path="1.png",
        question="question",
        reference_answer="reference",
        candidate_a="A",
        candidate_b="B",
    )


def test_arena_keeps_candidate_names_when_reversed(project_root) -> None:
    normal = build_arena_case(_pair())
    reversed_case = build_arena_case(_pair(), reverse=True)

    assert [item.name for item in normal.contestants] == ["candidate_a", "candidate_b"]
    assert [item.name for item in reversed_case.contestants] == ["candidate_b", "candidate_a"]
    metric = build_arena_metric(NoCallJudge(), project_root / "configs/week-03-judge-rubric.yaml")
    assert metric.name == "OpenCQA Better Answer"


def test_tie_lookup_bug_is_kept_as_tie() -> None:
    class TieMetric:
        def measure(self, test_case, _show_indicator=False):
            del test_case, _show_indicator
            raise KeyError("tie")

    assert measure(TieMetric(), _pair()) == "tie"
