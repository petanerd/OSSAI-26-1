"""OpenCQA 차트 한 장에 Week 4 이미지 변형을 만든다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from verifiable_ai_workflow.image_robustness import generate_variants
from verifiable_ai_workflow.open_cqa_candidates import load_open_cqa_cases

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-number", type=int, default=1)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "local-data/opencqa/week-04-variants"
    )
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    cases = load_open_cqa_cases(PROJECT_ROOT / "local-data/opencqa/week-03-cases.jsonl")
    if not 1 <= args.pair_number <= len(cases):
        raise SystemExit(f"--pair-number는 1부터 {len(cases)}까지입니다")
    case = cases[args.pair_number - 1]
    source = PROJECT_ROOT / case.image_path
    artifacts = generate_variants(
        source_path=source,
        sample_id=case.sample_id,
        output_dir=args.output,
        config_path=PROJECT_ROOT / "configs/week-04.yaml",
        project_root=PROJECT_ROOT,
        expected_source_sha256=case.image_sha256,
    )
    (args.output / "variants.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in artifacts), encoding="utf-8"
    )
    review = args.output / "variant-review.csv"
    if not review.exists():
        with review.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "sample_id",
                    "variant_id",
                    "image_sha256",
                    "intended_behavior",
                    "grounding_status",
                ]
            )
            for item in artifacts:
                writer.writerow(
                    [
                        item.sample_id,
                        item.variant_id,
                        item.image_sha256,
                        item.intended_behavior,
                        "",
                    ]
                )
    (args.output / "case.json").write_text(
        json.dumps(
            {
                "pair_id": case.pair_id,
                "sample_id": case.sample_id,
                "family_id": case.family_id,
                "course_split": case.course_split,
                "source_split": case.source_split,
                "source_revision": case.source_revision,
                "source_license": case.source_license,
                "question": case.question,
                "reference_answer": case.reference_answer,
                "original_image": case.image_path,
                "original_image_sha256": case.image_sha256,
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
