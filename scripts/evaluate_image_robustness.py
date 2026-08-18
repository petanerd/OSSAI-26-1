"""원본·변형 VLM 응답을 근거 보존 여부에 맞게 채점한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verifiable_ai_workflow.image_robustness import (
    VariantArtifact,
    load_response_map,
    load_reviews,
    score_original,
    score_variant,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "local-data/opencqa/week-04-variants"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=Path, default=DEFAULT_ROOT / "variants.jsonl")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_ROOT / "variant-review.csv")
    parser.add_argument("--case", type=Path, default=DEFAULT_ROOT / "case.json")
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
    case = json.loads(args.case.read_text(encoding="utf-8"))
    reviews = load_reviews(
        args.reviews,
        artifacts,
        project_root=PROJECT_ROOT,
        source_path=PROJECT_ROOT / case["original_image"],
    )
    responses = load_response_map(args.responses)
    required = {"original", *(item.variant_id for item in artifacts)}
    if set(responses) != required:
        raise SystemExit(f"응답 ID가 다릅니다: required={sorted(required)}")
    scores = [score_original(case["reference_answer"], responses["original"])] + [
        score_variant(
            item,
            reviews[item.variant_id],
            case["reference_answer"],
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
    source_summary_path = args.responses.parent / "summary.json"
    source_summary = (
        json.loads(source_summary_path.read_text(encoding="utf-8"))
        if source_summary_path.is_file()
        else {}
    )
    manifest = {
        "source_git_sha": source_summary.get("git_sha"),
        "evaluation_sha256": _sha256(args.output),
        "responses_sha256": _sha256(args.responses),
        "case_sha256": _sha256(args.case),
        "variants_sha256": _sha256(args.variants),
        "reviews_sha256": _sha256(args.reviews),
        "scorer_sha256": _sha256(
            PROJECT_ROOT / "src/verifiable_ai_workflow/image_robustness.py"
        ),
        "metric_sha256": _sha256(
            PROJECT_ROOT / "src/verifiable_ai_workflow/prompt_optimization.py"
        ),
        "schema_sha256": _sha256(
            PROJECT_ROOT / "src/verifiable_ai_workflow/schemas/models.py"
        ),
    }
    (args.output.parent / "evaluation-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"통과={sum(item.status == 'passed' for item in scores)}, "
        f"실패={sum(item.status == 'failed' for item in scores)}, "
        f"판정 불가={sum(item.status == 'inconclusive' for item in scores)}, "
        f"변형 무효={sum(item.status == 'invalid_variant' for item in scores)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
