import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.prepare_opencqa import SELECTION, _candidate_order, prepare


def test_candidate_order_is_stable() -> None:
    assert _candidate_order("19", "abstract", "extract") == _candidate_order(
        "19", "abstract", "extract"
    )
    assert set(_candidate_order("19", "abstract", "extract")) == {"abstract", "extract"}


def test_selection_has_30_unique_pairs() -> None:
    sample_ids = yaml.safe_load(SELECTION.read_text(encoding="utf-8"))["sample_ids"]
    assert len(sample_ids) == len(set(sample_ids)) == 30


def test_prepare_uses_images_and_questions_only(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "OpenCQA"
    annotation = source / "etc/data(full_summary_article)"
    images = source / "chart_images"
    annotation.mkdir(parents=True)
    images.mkdir()
    (images / "19.png").write_bytes(b"image")
    (annotation / "val_extended.json").write_text(
        json.dumps(
            {
                "19": [
                    "19.png",
                    "title must not be copied",
                    "article must not be copied",
                    "summary must not be copied",
                    "question",
                    "abstractive answer",
                    "extractive answer",
                ]
            }
        ),
        encoding="utf-8",
    )
    selection = yaml.safe_load(SELECTION.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, selection["revision"], ""),
    )
    custom_selection = tmp_path / "selection.yaml"
    custom_selection.write_text(
        yaml.safe_dump({**selection, "sample_ids": ["19"]}), encoding="utf-8"
    )
    monkeypatch.setattr("scripts.prepare_opencqa.SELECTION", custom_selection)

    output = tmp_path / "output"
    pairs = prepare(source, output)

    assert pairs[0]["question"] == "question"
    assert pairs[0]["reference_answer"] == "abstractive answer"
    assert "article" not in pairs[0]
    assert "summary" not in pairs[0]
    assert (output / "images/19.png").read_bytes() == b"image"
    labels = (output / "week-03-reviewer-1.csv").read_text(encoding="utf-8")
    assert labels == "pair_id,label\nopencqa-val-19,\n"

    original_pairs = (output / "week-03-pairs.jsonl").read_text(encoding="utf-8")
    (output / "week-03-reviewer-1.csv").write_text(
        "pair_id,label\nopencqa-val-old,\n", encoding="utf-8"
    )
    source_rows = json.loads((annotation / "val_extended.json").read_text(encoding="utf-8"))
    source_rows["19"][5] = "changed answer"
    (annotation / "val_extended.json").write_text(json.dumps(source_rows), encoding="utf-8")
    with pytest.raises(ValueError, match="pair ID"):
        prepare(source, output)
    assert (output / "week-03-pairs.jsonl").read_text(encoding="utf-8") == original_pairs
