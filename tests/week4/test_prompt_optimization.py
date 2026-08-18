import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from deepeval.models import DeepEvalBaseLLM
from deepeval.prompt import Prompt

from scripts import optimize_open_cqa_prompt
from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.open_cqa_candidates import OpenCQACase
from verifiable_ai_workflow.prompt_optimization import (
    OpenCqaDeterministicMetric,
    OpenCqaVlmCallback,
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


def _cases() -> list[OpenCQACase]:
    return [
        OpenCQACase(
            pair_id=f"pair-{index}",
            sample_id=str(index),
            family_id=f"family-{index}",
            course_split=(
                "development" if index < 18 else "validation" if index < 24 else "test"
            ),
            source_split="val",
            source_revision="a" * 40,
            source_license="GPL-3.0",
            image_sha256="b" * 64,
            image_path=f"{index}.png",
            question="What changed?",
            reference_answer="It rose from 10% to 20%.",
        )
        for index in range(30)
    ]


def test_split_is_18_6_6_and_optimizer_uses_development(project_root: Path) -> None:
    splits = split_goldens(list(reversed(_cases())))

    assert {name: len(items) for name, items in splits.items()} == {
        "development": 18,
        "validation": 6,
        "test": 6,
    }
    assert all(
        (golden.additional_metadata or {})["split"] == split
        for split, goldens in splits.items()
        for golden in goldens
    )
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
    golden = split_goldens(_cases())["development"][0]
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

    assert result["pair_id"] == "pair-0"
    assert result["sample_id"] == "0"
    assert result["image_path"] == "0.png"
    assert result["split"] == "development"
    assert 0 < result["score"] < 1
    assert "10%" in result["reason"]


def test_baseline_prompt_interpolates_question(project_root: Path) -> None:
    prompt = Prompt(text_template=(project_root / "prompts/week-04-baseline.md").read_text())
    rendered = prompt.interpolate(question="What changed?")
    assert "What changed?" in rendered
    assert all(field in rendered for field in ("evidence", "abstained", "답변 보류"))


def test_vlm_callback_labels_jpeg_input_correctly(tmp_path: Path) -> None:
    image = tmp_path / "chart.jpg"
    image.write_bytes(b"jpeg")

    class Provider:
        messages: list[dict] | None = None

        def generate(self, sample_id, messages):
            assert sample_id == "0"
            self.messages = messages
            return "{}"

    provider = Provider()
    golden = split_goldens(_cases())["development"][0]
    golden.additional_metadata["image_path"] = image.name

    OpenCqaVlmCallback(provider, tmp_path)(Prompt(text_template="{question}"), golden)

    assert provider.messages is not None
    data_url = provider.messages[1]["content"][1]["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")


def test_optimizer_separates_nim_target_and_gemini_review() -> None:
    target = load_settings(optimize_open_cqa_prompt.TARGET_CONFIG)
    optimizer = load_settings(optimize_open_cqa_prompt.OPTIMIZER_CONFIG)

    assert target.provider.model == "nvidia_nim/google/gemma-4-31b-it"
    assert optimizer.provider.model == "gemini/gemini-3.5-flash-lite"


def test_identical_candidate_cannot_win_from_repeated_model_variation() -> None:
    baseline = Prompt(text_template="same {question}")
    candidate = Prompt(text_template="same {question}")

    selected, prompt, reason = optimize_open_cqa_prompt._select_prompt(
        baseline, candidate, baseline_mean=0.1, candidate_mean=0.9
    )

    assert (selected, prompt, reason) == (
        "baseline",
        baseline,
        "candidate_identical",
    )


@pytest.mark.parametrize(
    ("catalog_date", "pricing_date"),
    [
        ("2000-01-01", date.today().isoformat()),
        (date.today().isoformat(), "2000-01-01"),
    ],
)
def test_optimizer_rejects_stale_preflight_before_live_work(
    monkeypatch,
    tmp_path,
    catalog_date,
    pricing_date,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "optimize_open_cqa_prompt.py",
            "--live-optimize",
            "--max-requests",
            "9",
            "--max-input-tokens",
            "180000",
            "--max-output-tokens",
            "4500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "600",
            "--catalog-verified-on",
            catalog_date,
            "--pricing-verified-on",
            pricing_date,
            "--optimizer-max-requests",
            "4",
            "--optimizer-max-attempts",
            "8",
            "--optimizer-max-input-tokens",
            "40000",
            "--optimizer-max-output-tokens",
            "16000",
            "--optimizer-max-cost-usd",
            "0.01",
            "--optimizer-max-wall-seconds",
            "7200",
            "--optimizer-catalog-verified-on",
            date.today().isoformat(),
            "--optimizer-pricing-verified-on",
            date.today().isoformat(),
            "--output",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit, match="실행 당일"):
        optimize_open_cqa_prompt.main()


def test_optimizer_rejects_larger_than_approved_caps(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "optimize_open_cqa_prompt.py",
            "--live-optimize",
            "--max-requests",
            "46",
            "--max-input-tokens",
            "900000",
            "--max-output-tokens",
            "22500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "7200",
            "--catalog-verified-on",
            date.today().isoformat(),
            "--pricing-verified-on",
            date.today().isoformat(),
            "--optimizer-max-requests",
            "4",
            "--optimizer-max-attempts",
            "8",
            "--optimizer-max-input-tokens",
            "40000",
            "--optimizer-max-output-tokens",
            "16000",
            "--optimizer-max-cost-usd",
            "0.01",
            "--optimizer-max-wall-seconds",
            "7200",
            "--optimizer-catalog-verified-on",
            date.today().isoformat(),
            "--optimizer-pricing-verified-on",
            date.today().isoformat(),
            "--output",
            str(tmp_path / "oversized"),
        ],
    )

    with pytest.raises(SystemExit, match="승인 cap"):
        optimize_open_cqa_prompt.main()


def test_optimizer_connection_error_without_response_is_inconclusive(
    monkeypatch, tmp_path
) -> None:
    class Provider:
        structured_output = "json_schema"
        last_call = {
            "provider_status": "provider_error",
            "error_type": "APIConnectionError",
        }
        budget = SimpleNamespace(summary=lambda: {"request_count": 1})

        def __init__(self, settings, output_ceiling) -> None:
            self.model = settings.provider.model
            self.expected_actual_model = settings.provider.expected_actual_model
            self.request_output_token_ceiling = output_ceiling

    class Optimizer:
        def optimize(self, prompt, goldens):
            del prompt, goldens
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(optimize_open_cqa_prompt, "_clean_git", lambda: "a" * 40)
    monkeypatch.setattr(optimize_open_cqa_prompt, "load_project_env", lambda path: path)
    monkeypatch.setattr(
        optimize_open_cqa_prompt,
        "build_course_provider",
        lambda settings, caps, **kwargs: Provider(
            settings,
            kwargs.get("request_output_token_ceiling")
            or settings.limits.request_output_token_ceiling,
        ),
    )
    monkeypatch.setattr(
        optimize_open_cqa_prompt,
        "load_open_cqa_cases",
        lambda path: _cases(),
    )
    monkeypatch.setattr(
        optimize_open_cqa_prompt,
        "build_prompt_optimizer",
        lambda **kwargs: Optimizer(),
    )
    output = tmp_path / "failed"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "optimize_open_cqa_prompt.py",
            "--live-optimize",
            "--max-requests",
            "45",
            "--max-input-tokens",
            "900000",
            "--max-output-tokens",
            "22500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "7200",
            "--catalog-verified-on",
            date.today().isoformat(),
            "--pricing-verified-on",
            date.today().isoformat(),
            "--optimizer-max-requests",
            "4",
            "--optimizer-max-attempts",
            "8",
            "--optimizer-max-input-tokens",
            "40000",
            "--optimizer-max-output-tokens",
            "16000",
            "--optimizer-max-cost-usd",
            "0.01",
            "--optimizer-max-wall-seconds",
            "7200",
            "--optimizer-catalog-verified-on",
            date.today().isoformat(),
            "--optimizer-pricing-verified-on",
            date.today().isoformat(),
            "--output",
            str(output),
        ],
    )

    assert optimize_open_cqa_prompt.main() == 2
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "inconclusive"
    assert summary["observed_status"] == "inconclusive"
    assert summary["error_type"] == "RuntimeError"
    assert summary["source_revision"] == "a" * 40
    assert len(summary["split_sample_ids"]["test"]) == 6
    assert summary["target_provider"]["pricing_verified_on"] == date.today().isoformat()
    assert summary["optimizer_provider"]["pricing_verified_on"] == date.today().isoformat()
    assert summary["target_provider"]["requested_model"].startswith("nvidia_nim/")
    assert summary["optimizer_provider"]["requested_model"].startswith("gemini/")
    assert summary["artifact_sha256"]["calls.jsonl"]
    assert summary["baseline_prompt_sha256"]
    assert summary["schema_sha256"]
    assert summary["scorer_sha256"]
    assert summary["optimizer_config_sha256"]
    calls = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {call["provider_role"] for call in calls} == {"target", "optimizer"}
    assert all(call["error_type"] == "APIConnectionError" for call in calls)
