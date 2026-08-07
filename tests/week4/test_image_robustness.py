import csv
from pathlib import Path

from PIL import Image

from verifiable_ai_workflow.image_robustness import (
    generate_variants,
    load_reviews,
    score_original,
    score_variant,
)
from verifiable_ai_workflow.schemas import Evidence, StructuredAnswer


def _answer(value: str = "47%", *, abstained: bool = False) -> StructuredAnswer:
    return StructuredAnswer(
        answer="답변 보류" if abstained else value,
        evidence=(
            []
            if abstained
            else [Evidence(evidence_id="chart#page=1", quote=value, page_number=1)]
        ),
        confidence=0,
        abstained=abstained,
        abstention_reason="근거가 가려짐" if abstained else None,
    )


def test_generate_four_variants_and_score_by_human_review(
    tmp_path: Path,
    project_root: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (200, 100), "white").save(source)
    artifacts = generate_variants(
        source_path=source,
        sample_id="19",
        output_dir=tmp_path / "variants",
        config_path=project_root / "configs/week-04.yaml",
    )

    assert len(artifacts) == 4
    assert len({item.image_sha256 for item in artifacts}) == 4
    preserved = next(item for item in artifacts if item.intended_behavior == "invariance")
    destroyed = next(
        item for item in artifacts if item.intended_behavior == "graceful_degradation"
    )
    assert score_variant(preserved, "preserved", _answer(), _answer()).status == "passed"
    destroyed_result = score_variant(destroyed, "destroyed", _answer(), _answer(abstained=True))
    assert destroyed_result.status == "passed"
    assert score_variant(destroyed, "preserved", _answer(), _answer()).status == "invalid_variant"


def test_review_must_be_completed(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant_id", "intended_behavior", "grounding_status"])
        writer.writerow(["crop", "graceful_degradation", ""])

    try:
        load_reviews(path)
    except ValueError as exc:
        assert "grounding_status" in str(exc)
    else:
        raise AssertionError("빈 사람 검토가 통과하면 안 됩니다")


def test_original_compares_reference_numbers() -> None:
    assert score_original("It rose from 10% to 20%.", _answer("10% and 20%")).status == "passed"
    assert score_original("It rose from 10% to 20%.", _answer("20%")).status == "failed"
