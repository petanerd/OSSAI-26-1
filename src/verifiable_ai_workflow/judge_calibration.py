"""OpenCQA 사람 라벨과 반복 Judge 결과를 비교한다."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Preference = Literal["candidate_a", "tie", "candidate_b"]
_PREFERENCES: tuple[Preference, ...] = ("candidate_a", "tie", "candidate_b")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JudgePair(StrictModel):
    pair_id: str
    sample_id: str
    image_path: str
    question: str
    reference_answer: str
    candidate_a: str
    candidate_b: str


class HumanLabel(StrictModel):
    pair_id: str
    reviewer_1: Preference
    reviewer_2: Preference
    adjudicated: Preference


class JudgeTrial(StrictModel):
    pair_id: str
    trial: Literal[1, 2]
    winner_ab: Preference
    winner_ba: Preference


class PairAudit(StrictModel):
    pair_id: str
    human_label: Preference
    judge_label: Preference | Literal["review"]
    order_conflict: bool
    repetition_conflict: bool
    agrees_with_human: bool


class CalibrationSummary(StrictModel):
    pair_count: int = Field(ge=1)
    evidence_kind: Literal["exploratory", "live_quality"]
    human_human_weighted_kappa: float
    judge_human_agreement: float = Field(ge=0, le=1)
    order_conflicts: int = Field(ge=0)
    repetition_conflicts: int = Field(ge=0)
    blocking_eligible: bool
    recommended_use: Literal["blocking", "diagnostic"]
    reasons: list[str]
    pairs: list[PairAudit]


def _jsonl(path: str | Path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_pairs(path: str | Path) -> list[JudgePair]:
    pairs = [JudgePair.model_validate(item) for item in _jsonl(path)]
    if not pairs or len({pair.pair_id for pair in pairs}) != len(pairs):
        raise ValueError("pair는 비어 있거나 pair_id가 중복될 수 없습니다")
    return pairs


def load_human_labels(path: str | Path) -> list[HumanLabel]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    try:
        labels = [HumanLabel.model_validate(row) for row in rows]
    except Exception as exc:
        raise ValueError(
            "사람 라벨을 모두 입력하세요: candidate_a, tie, candidate_b 중 하나여야 합니다"
        ) from exc
    if not labels or len({label.pair_id for label in labels}) != len(labels):
        raise ValueError("사람 라벨은 비어 있거나 pair_id가 중복될 수 없습니다")
    return labels


def load_judge_trials(path: str | Path) -> list[JudgeTrial]:
    trials = [JudgeTrial.model_validate(item) for item in _jsonl(path)]
    if len({(item.pair_id, item.trial) for item in trials}) != len(trials):
        raise ValueError("같은 pair_id와 trial이 중복되었습니다")
    return trials


def weighted_cohen_kappa(left: list[Preference], right: list[Preference]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("같은 길이의 비어 있지 않은 두 사람 라벨이 필요합니다")
    index = {label: number for number, label in enumerate(_PREFERENCES)}
    observed = sum(abs(index[a] - index[b]) / 2 for a, b in zip(left, right, strict=True))
    observed /= len(left)
    left_counts, right_counts = Counter(left), Counter(right)
    expected = sum(
        left_counts[a] / len(left) * right_counts[b] / len(right) * abs(index[a] - index[b]) / 2
        for a in _PREFERENCES
        for b in _PREFERENCES
    )
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - observed / expected


def calibrate(
    pairs: list[JudgePair],
    human_labels: list[HumanLabel],
    judge_trials: list[JudgeTrial],
    *,
    live_quality: bool = False,
) -> CalibrationSummary:
    pair_ids = {pair.pair_id for pair in pairs}
    human = {label.pair_id: label for label in human_labels}
    trials = {(item.pair_id, item.trial): item for item in judge_trials}
    if set(human) != pair_ids:
        raise ValueError("pair와 사람 라벨의 ID가 다릅니다")
    if {pair_id for pair_id, _trial in trials} != pair_ids or any(
        (pair_id, trial) not in trials for pair_id in pair_ids for trial in (1, 2)
    ):
        raise ValueError("모든 pair에 Judge trial 1과 2가 필요합니다")

    audits: list[PairAudit] = []
    for pair in pairs:
        first, second = trials[(pair.pair_id, 1)], trials[(pair.pair_id, 2)]
        first_label = first.winner_ab if first.winner_ab == first.winner_ba else "review"
        second_label = second.winner_ab if second.winner_ab == second.winner_ba else "review"
        order_conflict = "review" in (first_label, second_label)
        repetition_conflict = first_label != second_label
        judge_label = first_label if not order_conflict and not repetition_conflict else "review"
        expected = human[pair.pair_id].adjudicated
        audits.append(
            PairAudit(
                pair_id=pair.pair_id,
                human_label=expected,
                judge_label=judge_label,
                order_conflict=order_conflict,
                repetition_conflict=repetition_conflict,
                agrees_with_human=judge_label == expected,
            )
        )

    kappa = weighted_cohen_kappa(
        [human[pair.pair_id].reviewer_1 for pair in pairs],
        [human[pair.pair_id].reviewer_2 for pair in pairs],
    )
    agreement = sum(item.agrees_with_human for item in audits) / len(audits)
    order_conflicts = sum(item.order_conflict for item in audits)
    repetition_conflicts = sum(item.repetition_conflict for item in audits)
    reasons: list[str] = []
    if len(pairs) < 30:
        reasons.append(f"pair_count={len(pairs)} < 30")
    if kappa < 0.6:
        reasons.append(f"human weighted kappa={kappa:.3f} < 0.600")
    if agreement < 0.8:
        reasons.append(f"Judge-human agreement={agreement:.3f} < 0.800")
    if order_conflicts:
        reasons.append(f"A/B-B/A conflict={order_conflicts}")
    if repetition_conflicts:
        reasons.append(f"repeat conflict={repetition_conflicts}")
    if not live_quality:
        reasons.append("30쌍 live_quality 실행 증거가 아님")
    blocking = not reasons and live_quality
    return CalibrationSummary(
        pair_count=len(pairs),
        evidence_kind="live_quality" if live_quality else "exploratory",
        human_human_weighted_kappa=kappa,
        judge_human_agreement=agreement,
        order_conflicts=order_conflicts,
        repetition_conflicts=repetition_conflicts,
        blocking_eligible=blocking,
        recommended_use="blocking" if blocking else "diagnostic",
        reasons=reasons,
        pairs=audits,
    )
