"""OpenCQA 차트 한 장에 Week 4 이미지 변형을 만든다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from verifiable_ai_workflow.image_robustness import generate_variants
from verifiable_ai_workflow.judge_calibration import load_pairs

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-number", type=int, default=1)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "local-data/opencqa/week-04-variants"
    )
    args = parser.parse_args()
    pairs = load_pairs(PROJECT_ROOT / "local-data/opencqa/week-03-pairs.jsonl")
    if not 1 <= args.pair_number <= len(pairs):
        raise SystemExit(f"--pair-number는 1부터 {len(pairs)}까지입니다")
    pair = pairs[args.pair_number - 1]
    source = PROJECT_ROOT / pair.image_path
    artifacts = generate_variants(
        source_path=source,
        sample_id=pair.sample_id,
        output_dir=args.output,
        config_path=PROJECT_ROOT / "configs/week-04.yaml",
    )
    (args.output / "variants.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in artifacts), encoding="utf-8"
    )
    review = args.output / "variant-review.csv"
    if not review.exists():
        with review.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["variant_id", "intended_behavior", "grounding_status"])
            for item in artifacts:
                writer.writerow([item.variant_id, item.intended_behavior, ""])
    (args.output / "case.json").write_text(
        json.dumps(
            {
                "sample_id": pair.sample_id,
                "question": pair.question,
                "reference_answer": pair.reference_answer,
                "original_image": pair.image_path,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"이미지 변형 {len(artifacts)}개와 검토표를 {args.output}에 만들었습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
