import csv
from pathlib import Path

import pytest

from verifiable_ai_workflow.judge_calibration import (
    HumanLabel,
    JudgePair,
    JudgeTrial,
    calibrate,
    load_human_labels,
)


def _pairs(count: int = 30) -> list[JudgePair]:
    return [
        JudgePair(
            pair_id=f"pair-{index:02d}",
            sample_id=str(index),
            image_path=f"{index}.png",
            question="question",
            reference_answer="reference",
            candidate_a="A",
            candidate_b="B",
        )
        for index in range(count)
    ]


def _labels(pairs: list[JudgePair]) -> list[HumanLabel]:
    return [
        HumanLabel(
            pair_id=pair.pair_id,
            reviewer_1="candidate_a",
            reviewer_2="candidate_a",
            adjudicated="candidate_a",
        )
        for pair in pairs
    ]


def _trials(pairs: list[JudgePair]) -> list[JudgeTrial]:
    return [
        JudgeTrial(
            pair_id=pair.pair_id,
            trial=trial,
            winner_ab="candidate_a",
            winner_ba="candidate_a",
        )
        for pair in pairs
        for trial in (1, 2)
    ]


def test_complete_stable_calibration_can_be_blocking() -> None:
    pairs = _pairs()
    summary = calibrate(pairs, _labels(pairs), _trials(pairs), live_quality=True)

    assert summary.blocking_eligible
    assert summary.judge_human_agreement == 1
    assert summary.order_conflicts == 0


def test_order_or_repeat_change_goes_to_review() -> None:
    pairs = _pairs()
    trials = _trials(pairs)
    trials[0] = trials[0].model_copy(update={"winner_ba": "candidate_b"})

    summary = calibrate(pairs, _labels(pairs), trials)

    assert not summary.blocking_eligible
    assert summary.pairs[0].judge_label == "review"
    assert summary.order_conflicts == 1
    assert summary.repetition_conflicts == 1


def test_blank_human_labels_fail_as_incomplete(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair_id", "reviewer_1", "reviewer_2", "adjudicated"])
        writer.writerow(["pair-01", "", "", ""])

    with pytest.raises(ValueError, match="사람 라벨을 모두"):
        load_human_labels(path)


def test_missing_second_trial_fails() -> None:
    pairs = _pairs()
    with pytest.raises(ValueError, match="trial 1과 2"):
        calibrate(pairs, _labels(pairs), _trials(pairs)[:-1])
