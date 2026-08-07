"""공식 OpenCQA clone에서 Week 3 로컬 실습 자료를 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELECTION = PROJECT_ROOT / "data/opencqa/week-03-selection.yaml"
OUTPUT_ROOT = PROJECT_ROOT / "local-data/opencqa"


def _candidate_order(sample_id: str, abstractive: str, extractive: str) -> tuple[str, str]:
    """ID hash로 답의 위치를 섞어 한 답 유형이 항상 A가 되지 않게 한다."""

    if int(hashlib.sha256(sample_id.encode()).hexdigest(), 16) % 2:
        return abstractive, extractive
    return extractive, abstractive


def _git_revision(source_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def prepare(source_root: Path, output_root: Path = OUTPUT_ROOT) -> list[dict[str, str]]:
    selection = yaml.safe_load(SELECTION.read_text(encoding="utf-8"))
    if _git_revision(source_root) != selection["revision"]:
        raise ValueError("OpenCQA revision이 week-03-selection.yaml과 다릅니다")

    annotation = source_root / "etc/data(full_summary_article)/val_extended.json"
    chart_root = source_root / "chart_images"
    if not annotation.is_file() or not chart_root.is_dir():
        raise FileNotFoundError("OpenCQA annotation 또는 chart_images를 찾을 수 없습니다")
    source = json.loads(annotation.read_text(encoding="utf-8"))

    image_output = output_root / "images"
    image_output.mkdir(parents=True, exist_ok=True)
    pairs: list[dict[str, str]] = []
    for sample_id in selection["sample_ids"]:
        try:
            image_name, _title, _article, _summary, question, abstractive, extractive = source[
                sample_id
            ]
        except KeyError as exc:
            raise ValueError(f"OpenCQA val split에 sample {sample_id}가 없습니다") from exc
        source_image = chart_root / image_name
        if not source_image.is_file():
            raise FileNotFoundError(f"OpenCQA chart image가 없습니다: {source_image}")
        shutil.copy2(source_image, image_output / image_name)
        candidate_a, candidate_b = _candidate_order(sample_id, abstractive, extractive)
        pairs.append(
            {
                "pair_id": f"opencqa-val-{sample_id}",
                "sample_id": sample_id,
                "image_path": f"local-data/opencqa/images/{image_name}",
                "question": question,
                "reference_answer": abstractive,
                "candidate_a": candidate_a,
                "candidate_b": candidate_b,
            }
        )

    pairs_path = output_root / "week-03-pairs.jsonl"
    pairs_path.write_text(
        "".join(json.dumps(pair, ensure_ascii=False) + "\n" for pair in pairs),
        encoding="utf-8",
    )
    for reviewer in (1, 2):
        labels_path = output_root / f"week-03-reviewer-{reviewer}.csv"
        if labels_path.exists():
            continue
        with labels_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["pair_id", "label"])
            writer.writeheader()
            writer.writerows({"pair_id": pair["pair_id"]} for pair in pairs)
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    pairs = prepare(args.source_root.resolve())
    print(f"OpenCQA Week 3 pair {len(pairs)}개를 local-data/opencqa에 준비했습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
