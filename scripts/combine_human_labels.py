"""서로 보지 않고 작성한 두 사람의 OpenCQA 라벨을 합친다."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ALLOWED = {"candidate_a", "tie", "candidate_b"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "local-data/opencqa"


def _load(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    labels = {row["pair_id"]: row["label"] for row in rows}
    invalid = any(label not in ALLOWED for label in labels.values())
    if len(labels) != len(rows) or not labels or invalid:
        raise ValueError(f"{path.name}의 모든 label을 먼저 입력하세요")
    return labels


def combine(first_path: Path, second_path: Path, output: Path) -> int:
    first, second = _load(first_path), _load(second_path)
    if first.keys() != second.keys():
        raise ValueError("두 검토자의 pair_id가 다릅니다")
    if output.exists():
        raise FileExistsError(f"기존 조정 파일을 덮어쓰지 않습니다: {output}")
    disagreements = 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["pair_id", "reviewer_1", "reviewer_2", "adjudicated"],
        )
        writer.writeheader()
        for pair_id in first:
            same = first[pair_id] == second[pair_id]
            disagreements += not same
            writer.writerow(
                {
                    "pair_id": pair_id,
                    "reviewer_1": first[pair_id],
                    "reviewer_2": second[pair_id],
                    "adjudicated": first[pair_id] if same else "",
                }
            )
    return disagreements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer-1", type=Path, default=DATA / "week-03-reviewer-1.csv")
    parser.add_argument("--reviewer-2", type=Path, default=DATA / "week-03-reviewer-2.csv")
    parser.add_argument("--output", type=Path, default=DATA / "week-03-human-labels.csv")
    args = parser.parse_args()
    disagreements = combine(args.reviewer_1, args.reviewer_2, args.output)
    print(f"불일치 {disagreements}건은 {args.output.name}의 adjudicated 열을 직접 채우세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
