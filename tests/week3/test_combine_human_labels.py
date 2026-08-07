import csv
from pathlib import Path

from scripts.combine_human_labels import combine


def _write(path: Path, labels: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair_id", "label"])
        for index, label in enumerate(labels):
            writer.writerow([f"pair-{index}", label])


def test_disagreement_is_left_for_adjudication(tmp_path: Path) -> None:
    first, second, output = tmp_path / "first.csv", tmp_path / "second.csv", tmp_path / "out.csv"
    _write(first, ["candidate_a", "tie"])
    _write(second, ["candidate_a", "candidate_b"])

    assert combine(first, second, output) == 1
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["adjudicated"] == "candidate_a"
    assert rows[1]["adjudicated"] == ""
