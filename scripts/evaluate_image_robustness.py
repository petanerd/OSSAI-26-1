"""원본·변형 VLM 응답을 근거 보존 여부에 맞게 채점한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verifiable_ai_workflow.image_robustness import (
    VariantArtifact,
    load_response_map,
    load_reviews,
    score_variant,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "local-data/opencqa/week-04-variants"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=Path, default=DEFAULT_ROOT / "variants.jsonl")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_ROOT / "variant-review.csv")
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "reports/week-04/robustness.json"
    )
    args = parser.parse_args()
    artifacts = [
        VariantArtifact.model_validate_json(line)
        for line in args.variants.read_text().splitlines()
        if line.strip()
    ]
    reviews, responses = load_reviews(args.reviews), load_response_map(args.responses)
    required = {"original", *(item.variant_id for item in artifacts)}
    if set(responses) != required:
        raise SystemExit(f"응답 ID가 다릅니다: required={sorted(required)}")
    scores = [
        score_variant(
            item,
            reviews[item.variant_id],
            responses["original"],
            responses[item.variant_id],
        )
        for item in artifacts
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([item.model_dump() for item in scores], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"통과={sum(item.status == 'passed' for item in scores)}, "
        f"실패={sum(item.status == 'failed' for item in scores)}, "
        f"변형 무효={sum(item.status == 'invalid_variant' for item in scores)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
